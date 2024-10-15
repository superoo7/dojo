import json
from typing import List

import torch
from bittensor.btlogging import logging as logger
from strenum import StrEnum

from commons.exceptions import (
    InvalidCompletion,
    InvalidMinerResponse,
    InvalidTask,
)
from database.client import transaction
from database.mappers import (
    map_child_feedback_request_to_model,
    map_completion_response_to_model,
    map_criteria_type_to_model,
    map_parent_feedback_request_to_model,
)
from database.prisma._fields import Json
from database.prisma.models import Feedback_Request_Model, Score_Model
from database.prisma.types import Score_ModelCreateInput, Score_ModelUpdateInput
from dojo.protocol import (
    FeedbackRequest,
    RidToHotKeyToTaskId,
    RidToModelMap,
    TaskExpiryDict,
)


# TODO @oom remove this, it's unnecessary since we have prisma
class ValidatorStateKeys(StrEnum):
    SCORES = "scores"
    DOJO_TASKS_TO_TRACK = "dojo_tasks_to_track"
    MODEL_MAP = "model_map"
    TASK_TO_EXPIRY = "task_to_expiry"


""" This is essentially an ORM..."""


class DataManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    async def save_task(
        validator_request: FeedbackRequest, miner_responses: List[FeedbackRequest]
    ) -> Feedback_Request_Model | None:
        """Saves a task, which consists of both the validator's request and the miners' responses.

        Args:
            validator_request (FeedbackRequest): The request made by the validator.
            miner_responses (List[FeedbackRequest]): The responses made by the miners.

        Returns:
            Feedback_Request_Model | None: Only validator's feedback request model, or None if failed.
        """
        try:
            feedback_request_model: Feedback_Request_Model | None = None
            async with transaction() as tx:
                logger.trace("Starting transaction for saving task.")

                feedback_request_model = await tx.feedback_request_model.create(
                    data=map_parent_feedback_request_to_model(validator_request)
                )

                # Create related criteria types
                criteria_create_input = [
                    map_criteria_type_to_model(criteria, feedback_request_model.id)
                    for criteria in validator_request.criteria_types
                ]
                await tx.criteria_type_model.create_many(criteria_create_input)

                # Create related miner responses (child) and their completion responses
                created_miner_models: list[Feedback_Request_Model] = []
                for miner_response in miner_responses:
                    try:
                        create_miner_model_input = map_child_feedback_request_to_model(
                            miner_response,
                            feedback_request_model.id,
                            expire_at=feedback_request_model.expire_at,
                        )

                        created_miner_model = await tx.feedback_request_model.create(
                            data=create_miner_model_input
                        )

                        created_miner_models.append(created_miner_model)

                        # Create related completions for miner responses
                        for completion in miner_response.completion_responses:
                            completion_input = map_completion_response_to_model(
                                completion, created_miner_model.id
                            )
                            await tx.completion_response_model.create(
                                data=completion_input
                            )
                            logger.trace(
                                f"Created completion response: {completion_input}"
                            )

                    # we catch exceptions here because whether a miner responds well should not affect other miners
                    except InvalidMinerResponse as e:
                        miner_hotkey = (
                            miner_response.axon.hotkey if miner_response.axon else "??"
                        )
                        logger.debug(
                            f"Miner response from hotkey: {miner_hotkey} is invalid: {e}"
                        )
                    except InvalidCompletion as e:
                        miner_hotkey = (
                            miner_response.axon.hotkey if miner_response.axon else "??"
                        )
                        logger.debug(
                            f"Completion response from hotkey: {miner_hotkey} is invalid: {e}"
                        )

                if len(created_miner_models) == 0:
                    raise InvalidTask(
                        "A task must consist of at least one miner response, along with validator's request"
                    )

                feedback_request_model.child_requests = created_miner_models
            return feedback_request_model
        except Exception as e:
            logger.error(f"Failed to save dendrite query response: {e}")
            return None

    @classmethod
    async def overwrite_miner_responses_by_request_id(
        cls, request_id: str, miner_responses: List[FeedbackRequest]
    ) -> bool:
        try:
            # TODO can improve this
            async with transaction() as tx:
                # Delete existing completion responses for the given request_id
                await tx.completion_response_model.delete_many(
                    where={"miner_response": {"is": {"request_id": request_id}}}
                )

                # Delete existing miner responses for the given request_id
                await tx.miner_response_model.delete_many(
                    where={"request_id": request_id}
                )

                # Create new miner responses
                for miner_response in miner_responses:
                    miner_response_model = await tx.miner_response_model.create(
                        data=map_miner_response_to_model(miner_response, request_id)
                    )

                    # Create related completions for miner responses
                    for completion in miner_response.completion_responses:
                        await tx.completion_response_model.create(
                            data=map_completion_response_to_model(
                                completion, miner_response_model.id
                            )
                        )

            logger.success(f"Overwritten miner responses for requestId: {request_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to overwrite miner responses: {e}")
            return False

    @classmethod
    async def validator_save(
        cls,
        scores: torch.Tensor,
        requestid_to_mhotkey_to_task_id: RidToHotKeyToTaskId,
        model_map: RidToModelMap,
        task_to_expiry: TaskExpiryDict,
    ):
        """Saves the state of the validator to the database."""
        if cls._instance and cls._instance.step == 0:
            return
        try:
            dojo_task_data = json.loads(json.dumps(requestid_to_mhotkey_to_task_id))
            if not dojo_task_data and torch.count_nonzero(scores).item() == 0:
                raise ValueError("Dojo task data and scores are empty. Skipping save.")

            logger.trace(f"Saving validator dojo_task_data: {dojo_task_data}")
            logger.trace(f"Saving validator score: {scores}")

            # Convert tensors to lists for JSON serialization
            scores_list = scores.tolist()

            # Prepare nested data for creating the validator state
            validator_state_data: list[Validator_State_ModelCreateInput] = [
                {
                    "request_id": request_id,
                    "miner_hotkey": miner_hotkey,
                    "task_id": task_id,
                    "expire_at": task_to_expiry[task_id],
                    "obfuscated_model": obfuscated_model,
                    "real_model": real_model,
                }
                for request_id, hotkey_to_task in dojo_task_data.items()
                for miner_hotkey, task_id in hotkey_to_task.items()
                for obfuscated_model, real_model in model_map[request_id].items()
            ]

            # Save the validator state
            await Validator_State_Model.prisma().create_many(
                data=validator_state_data, skip_duplicates=True
            )

            if not torch.all(scores == 0):
                # Save scores as a single record
                score_model = await Score_Model.prisma().find_first()

                if score_model:
                    await Score_Model.prisma().update(
                        where={"id": score_model.id},
                        data=Score_ModelUpdateInput(
                            score=Json(json.dumps(scores_list))
                        ),
                    )
                else:
                    await Score_Model.prisma().create(
                        data=Score_ModelCreateInput(
                            score=Json(json.dumps(scores_list)),
                        )
                    )

                logger.success(
                    f"📦 Saved validator state with scores: {scores}, and for {len(dojo_task_data)} requests"
                )
            else:
                logger.warning("Scores are all zero. Skipping save.")
        except Exception as e:
            logger.error(f"Failed to save validator state: {e}")
