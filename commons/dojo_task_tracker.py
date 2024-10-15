import asyncio
import traceback
from collections import defaultdict

import bittensor as bt
from bittensor.btlogging import logging as logger

import dojo
from commons.exceptions import InvalidMinerResponse
from commons.objects import ObjectManager
from commons.orm import ORM
from dojo.protocol import (
    CriteriaTypeEnum,
    TaskResult,
    TaskResultRequest,
)


class DojoTaskTracker:
    _instance = None
    _should_exit: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def get_task_results_from_miner(
        cls, miner_hotkey: str, task_id: str
    ) -> list[TaskResult]:
        """Fetch task results from the miner's Axon using Dendrite."""
        try:
            logger.info(
                f"Fetching task result from miner {miner_hotkey} for task {task_id}"
            )

            validator = ObjectManager.get_validator()

            dendrite: bt.dendrite = validator.dendrite
            metagraph = validator.metagraph

            if not dendrite:
                raise ValueError("Dendrite not initialized")

            # Prepare the synapse (data request) that will be sent via Dendrite
            task_synapse = TaskResultRequest(task_id=task_id)

            # Use Dendrite to communicate with the Axon
            miner_axon = metagraph.axons[metagraph.hotkeys.index(miner_hotkey)]
            if not miner_axon:
                raise ValueError(f"Miner Axon not found for hotkey: {miner_hotkey}")

            # Send the request via Dendrite and get the response
            response = await dendrite.forward(
                axons=[miner_axon], synapse=task_synapse, deserialize=False
            )

            logger.debug(f"TaskResult Response from miner {miner_hotkey}: {response}")

            if response and response[0]:
                logger.info(
                    f"Received task result from miner {miner_hotkey} for task {task_id}"
                )
                return response[0].task_results
            else:
                logger.warning(
                    f"No task results found from miner {miner_hotkey} for task {task_id}"
                )
                return []

        except Exception as e:
            logger.error(f"Error fetching task result from miner {miner_hotkey}: {e}")
            return []

    @classmethod
    async def monitor_task_completions(cls):
        SLEEP_SECONDS = 30
        await asyncio.sleep(dojo.DOJO_TASK_MONITORING)

        while not cls._should_exit:
            try:
                validator = ObjectManager.get_validator()
                validator_hotkey = validator.wallet.hotkey.ss58_address
                batch_id = 0
                async for task_batch, has_more_batches in ORM.get_unexpired_tasks(
                    validator_hotkeys=[validator_hotkey],
                    batch_size=10,
                ):
                    if not has_more_batches:
                        logger.success(
                            "No more unexpired tasks found for processing, exiting task monitoring."
                        )
                        break

                    if not task_batch:
                        continue

                    logger.info(f"Monitoring task completions, batch id: {batch_id}")

                    for task in task_batch:
                        request_id = task.request.request_id
                        miner_responses = task.miner_responses

                        obfuscated_to_real_model_id = await ORM.get_real_model_ids(
                            request_id
                        )

                        for miner_response in miner_responses:
                            if (
                                not miner_response.axon
                                or not miner_response.axon.hotkey
                                or not miner_response.dojo_task_id
                            ):
                                raise InvalidMinerResponse(
                                    f"""Missing hotkey, task_id, or axon:
                                    axon: {miner_response.axon}
                                    hotkey: {miner_response.axon.hotkey}
                                    task_id: {miner_response.dojo_task_id}"""
                                )

                            miner_hotkey = miner_response.axon.hotkey
                            task_id = miner_response.dojo_task_id
                            task_results = await cls.get_task_results_from_miner(
                                miner_hotkey, task_id
                            )

                            if not task_results and not len(task_results) > 0:
                                logger.debug(
                                    f"Task ID: {task_id} by miner: {miner_hotkey} has not been completed yet or no task results."
                                )
                                continue

                            # Process task result
                            model_id_to_avg_rank, model_id_to_avg_score = (
                                cls._calculate_averages(
                                    task_results, obfuscated_to_real_model_id
                                )
                            )

                            # Update the response with the new ranks and scores
                            for completion in miner_response.completion_responses:
                                model_id = completion.model
                                if model_id in model_id_to_avg_rank:
                                    completion.rank_id = int(
                                        model_id_to_avg_rank[model_id]
                                    )
                                if model_id in model_id_to_avg_score:
                                    completion.score = model_id_to_avg_score[model_id]

                            # Update miner responses in the database
                            success = await ORM.update_miner_completions_by_request_id(
                                request_id, task.miner_responses
                            )

                            logger.info(
                                f"Updating task {request_id} with miner's completion data, success ? {success}"
                            )

            except Exception as e:
                traceback.print_exc()
                logger.error(f"Error during Dojo task monitoring {str(e)}")
                pass
            await asyncio.sleep(SLEEP_SECONDS)

    @staticmethod
    def _calculate_averages(
        task_results: list[TaskResult], obfuscated_to_real_model_id
    ):
        model_id_to_avg_rank = defaultdict(float)
        model_id_to_avg_score = defaultdict(float)
        num_ranks_by_workers, num_scores_by_workers = 0, 0

        for result in task_results:
            for result_data in result.result_data:
                type = result_data.type
                value = result_data.value
                if type == CriteriaTypeEnum.RANKING_CRITERIA:
                    for model_id, rank in value.items():
                        real_model_id = obfuscated_to_real_model_id.get(
                            model_id, model_id
                        )
                        model_id_to_avg_rank[real_model_id] += rank
                    num_ranks_by_workers += 1
                elif type == CriteriaTypeEnum.MULTI_SCORE:
                    for model_id, score in value.items():
                        real_model_id = obfuscated_to_real_model_id.get(
                            model_id, model_id
                        )
                        model_id_to_avg_score[real_model_id] += score
                    num_scores_by_workers += 1

        # Average the ranks and scores
        for model_id in model_id_to_avg_rank:
            model_id_to_avg_rank[model_id] /= num_ranks_by_workers
        for model_id in model_id_to_avg_score:
            model_id_to_avg_score[model_id] /= num_scores_by_workers

        return model_id_to_avg_rank, model_id_to_avg_score
