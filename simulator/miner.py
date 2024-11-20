import os
import redis
import traceback
import asyncio
import random
import json
from datetime import datetime, timezone
from typing import Dict, Optional

from bittensor.btlogging import logging as logger
from neurons.miner import Miner
from dojo.protocol import (
    FeedbackRequest,
    TaskResultRequest,
    TaskResult,
    Result,
    MultiScoreCriteria,
    CriteriaType
)
from commons.utils import get_new_uuid


class MinerSim(Miner):
    def __init__(self):
        super().__init__()
        try:
            # Initialize Redis connection
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", 6379))
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=0,
                decode_responses=True
            )
            
            # Configure simulation parameters
            self._configure_simulation()
            
            logger.info("Redis connection established")
            logger.info("Starting Miner Simulator")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def _configure_simulation(self):
        """Configure simulation parameters with environment variables or defaults."""
        self.response_behaviors = {
            'normal': float(os.getenv("SIM_NORMAL_RESP_PROB", 0.8)),
            'no_response': float(os.getenv("SIM_NO_RESP_PROB", 0.1)),
            'timeout': float(os.getenv("SIM_TIMEOUT_PROB", 0.1))
        }
        
        self.timeout_range = (
            float(os.getenv("SIM_MIN_TIMEOUT", 5)),
            float(os.getenv("SIM_MAX_TIMEOUT", 10))
        )

    async def forward_feedback_request(self, synapse: FeedbackRequest) -> FeedbackRequest:
        try:
            # Validate that synapse, dendrite, dendrite.hotkey, and response are not None
            if not synapse or not synapse.dendrite or not synapse.dendrite.hotkey:
                logger.error("Invalid synapse: dendrite or dendrite.hotkey is None.")
                return synapse

            if not synapse.completion_responses:
                logger.error("Invalid synapse: response field is None.")
                return synapse

            # Empty out completion response since not needed in simulator
            new_synapse = synapse.model_copy(deep=True)
            new_synapse.completion_responses = []

            synapse.dojo_task_id = synapse.request_id
            self.hotkey_to_request[synapse.dendrite.hotkey] = synapse

            redis_key = f"feedback:{synapse.request_id}"
            self.redis_client.set(
                redis_key,
                new_synapse.model_dump_json(),
                ex=36000  # expire after 10 hours
            )
            logger.info(f"Stored feedback request {synapse.request_id}")

            synapse.ground_truth = {}
            return synapse

        except Exception as e:
            logger.error(f"Error handling FeedbackRequest: {e}")
            traceback.print_exc()
            return synapse

    async def forward_task_result_request(self, synapse: TaskResultRequest) -> TaskResultRequest:
        try:
            logger.info(f"Received TaskResultRequest for task id: {synapse.task_id}")
            if not synapse or not synapse.task_id:
                logger.error("Invalid TaskResultRequest: missing task_id")
                return synapse

            # Simulate different response behaviors
            behavior = self._get_response_behavior()
            
            if behavior == 'no_response':
                logger.debug(f"Simulating no response for task {synapse.task_id}")
                return synapse
                
            if behavior == 'timeout':
                # Simulate a timeout by waiting
                logger.debug(f"Simulating timeout for task {synapse.task_id}")
                await asyncio.sleep(random.uniform(*self.timeout_range))
                return synapse

            redis_key = f"feedback:{synapse.task_id}"
            request_data = self.redis_client.get(redis_key)

            request_dict = json.loads(request_data) if request_data else None
            feedback_request = FeedbackRequest(**request_dict) if request_dict else None

            if not feedback_request:
                logger.debug(f"No task result found for task id: {synapse.task_id}")
                return synapse

            current_time = datetime.now(timezone.utc).isoformat()

            task_results = []
            for criteria_type in feedback_request.criteria_types:
                result = Result(
                    type=criteria_type.type,
                    value=self._generate_scores(feedback_request.ground_truth)
                )
                
                task_result = TaskResult(
                    id=get_new_uuid(),
                    status=self._get_task_status(behavior),
                    created_at=current_time,
                    updated_at=current_time,
                    result_data=[result],
                    worker_id=get_new_uuid(),
                    task_id=synapse.task_id
                )
                task_results.append(task_result)

            synapse.task_results = task_results
            logger.info(f"TaskResultRequest: {synapse}")

            self.redis_client.delete(redis_key)
            logger.debug(f"Processed task result for task {synapse.task_id}")
            
            return synapse

        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error handling TaskResultRequest: {e}")
            return synapse

    def _get_response_behavior(self) -> str:
        """Determine the response behavior based on configured probabilities."""
        return random.choices(
            list(self.response_behaviors.keys()), 
            weights=list(self.response_behaviors.values())
        )[0]

    def _get_task_status(self, behavior: str) -> str:
        """Determine task status based on behavior."""
        if behavior in ['timeout', 'no_response']:
            return 'FAILED'
        else:
            return 'COMPLETED'

    def _generate_scores(self, ground_truth: dict) -> dict:
        """Generate scores using the specific formula."""
        scores = {}
        
        for k, v in ground_truth.items():
            # Apply the exact formula: int(((int(v + random.uniform(-0.5, 0.5))) / (10 - 1)) * (100 - 1) + 1)
            score = int(((int(v + random.uniform(-0.5, 0.5))) / (10 - 1)) * (100 - 1) + 1)
            # Ensure score stays within bounds
            score = max(1, min(100, score))
            scores[k] = score
        
        return scores

    # def __del__(self):
    #     """Cleanup Redis connection on object destruction"""
    #     try:
    #         self.redis_client.close()
    #         logger.info("Redis connection closed")
    #     except:
    #         pass