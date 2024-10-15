import json

import torch
from bittensor.btlogging import logging as logger
from strenum import StrEnum

from database.prisma._fields import Json
from database.prisma.models import Score_Model
from database.prisma.types import Score_ModelCreateInput, Score_ModelUpdateInput
from dojo.protocol import (
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
