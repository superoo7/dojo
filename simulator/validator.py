import asyncio
from typing import List
import bittensor as bt
from dojo.protocol import FeedbackRequest
from neurons.validator import Validator
from bittensor.btlogging import logging as logger


class ValidatorSim(Validator):
    def __init__(self):
        super().__init__()
        logger.info("Starting Validator Simulator")

    @staticmethod
    async def _send_shuffled_requests(
            dendrite: bt.dendrite, axons: List[bt.AxonInfo], synapse: FeedbackRequest
    ) -> list[FeedbackRequest]:
        """Send the same request to all miners without shuffling the order.
         WARNING: This should only be used for testing/debugging as it could allow miners to game the system.

         Args:
             dendrite (bt.dendrite): Communication channel to send requests
             axons (List[bt.AxonInfo]): List of miner endpoints
             synapse (FeedbackRequest): The feedback request to send

         Returns:
             list[FeedbackRequest]: List of miner responses
         """
        all_responses = []
        batch_size = 10

        for i in range(0, len(axons), batch_size):
            batch_axons = axons[i: i + batch_size]
            tasks = []

            for axon in batch_axons:
                tasks.append(
                    dendrite.forward(
                        axons=[axon],
                        synapse=synapse,
                        deserialize=False,
                        timeout=12,
                    )
                )

            batch_responses = await asyncio.gather(*tasks)
            flat_batch_responses = [
                response for sublist in batch_responses for response in sublist
            ]
            all_responses.extend(flat_batch_responses)

            logger.info(
                f"Processed batch {i // batch_size + 1} of {(len(axons) - 1) // batch_size + 1}"
            )

        return all_responses
