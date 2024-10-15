from datetime import datetime, timezone
from typing import AsyncGenerator, List

from commons.exceptions import NoNewUnexpiredTasksYet, UnexpiredTasksAlreadyProcessed
from database.mappers import (
    map_feedback_request_model_to_feedback_request,
)
from database.prisma.models import (
    Feedback_Request_Model,
)
from database.prisma.types import (
    Feedback_Request_ModelInclude,
    Feedback_Request_ModelWhereInput,
)
from dojo import TASK_DEADLINE
from dojo.protocol import (
    DendriteQueryResponse,
)


class ORM:
    @staticmethod
    async def get_unexpired_tasks(
        validator_hotkeys: list[str],
        batch_size: int = 10,
    ) -> AsyncGenerator[tuple[List[DendriteQueryResponse], bool], None]:
        """Returns a batch of Feedback_Request_Model and a boolean indicating if there are more batches

        Args:
            validator_hotkeys (list[str]): List of validator hotkeys.
            batch_size (int, optional): Number of tasks to return in a batch. Defaults to 10.

            1 task == 1 validator request, N miner responses

        Yields:
            Iterator[AsyncGenerator[tuple[List[DendriteQueryResponse], bool], None]]:
                Returns a batch of DendriteQueryResponse and a boolean indicating if there are more batches

        """

        # find all validator requests first
        include_query = Feedback_Request_ModelInclude(
            {
                "completions": True,
                "criteria_types": True,
                "ground_truths": True,
                "parent_request": True,
            }
        )
        vali_where_query_unprocessed = Feedback_Request_ModelWhereInput(
            {
                "hotkey": {"in": validator_hotkeys, "mode": "insensitive"},
                "child_requests": {"some": {}},
                # only check for expire at since miner may lie
                "expire_at": {
                    "gt": datetime.now(timezone.utc),
                },
                "is_processed": {"equals": False},
            }
        )

        vali_where_query_processed = Feedback_Request_ModelWhereInput(
            {
                "hotkey": {"in": validator_hotkeys, "mode": "insensitive"},
                "child_requests": {"some": {}},
                # only check for expire at since miner may lie
                "expire_at": {
                    "gt": datetime.now(timezone.utc),
                },
                "is_processed": {"equals": True},
            }
        )

        # count first total including non
        task_count_unprocessed = await Feedback_Request_Model.prisma().count(
            where=vali_where_query_unprocessed,
        )

        task_count_processed = await Feedback_Request_Model.prisma().count(
            where=vali_where_query_processed,
        )

        if not task_count_unprocessed:
            if task_count_processed:
                raise UnexpiredTasksAlreadyProcessed(
                    f"No remaining unexpired tasks found for processing, but don't worry as you have processed {task_count_processed} tasks."
                )
            else:
                raise NoNewUnexpiredTasksYet(
                    f"No unexpired tasks found for processing, please wait for tasks to pass the task deadline of {TASK_DEADLINE} seconds."
                )

        for i in range(0, task_count_unprocessed, batch_size):
            # find all validator requests
            validator_requests = await Feedback_Request_Model.prisma().find_many(
                include=include_query,
                where=vali_where_query_unprocessed,
                order={"created_at": "desc"},
                skip=i,
                take=batch_size,
            )

            # find all miner responses
            validator_request_ids = [r.id for r in validator_requests]

            miner_responses = await Feedback_Request_Model.prisma().find_many(
                include=include_query,
                where={
                    "parent_id": {"in": validator_request_ids},
                },
                order={"created_at": "desc"},
            )

            responses: list[DendriteQueryResponse] = []
            for validator_request in validator_requests:
                vali_request = map_feedback_request_model_to_feedback_request(
                    validator_request
                )

                m_responses = list(
                    map(
                        lambda x: map_feedback_request_model_to_feedback_request(
                            x, is_miner=True
                        ),
                        [
                            m
                            for m in miner_responses
                            if m.parent_id == validator_request.id
                        ],
                    )
                )

                responses.append(
                    DendriteQueryResponse(
                        request=vali_request, miner_responses=m_responses
                    )
                )

            # yield responses, so caller can do something
            has_more_batches = True
            yield responses, has_more_batches

        yield [], False
