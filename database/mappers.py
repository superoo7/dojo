import json
from datetime import datetime, timezone

import bittensor as bt
from loguru import logger

import dojo
from commons.utils import is_valid_expiry, set_expire_time
from database.prisma import Json
from database.prisma.enums import CriteriaTypeEnum
from database.prisma.models import Criteria_Type_Model, Feedback_Request_Model
from database.prisma.types import (
    Completion_Response_ModelCreateInput,
    Criteria_Type_ModelCreateInput,
    Criteria_Type_ModelCreateWithoutRelationsInput,
    Feedback_Request_ModelCreateInput,
)
from dojo.protocol import (
    CompletionResponses,
    CriteriaType,
    FeedbackRequest,
    MultiScoreCriteria,
    MultiSelectCriteria,
    RankingCriteria,
    ScoreCriteria,
)


def map_criteria_type_to_model(
    criteria: CriteriaType, feedback_request_id: str
) -> Criteria_Type_ModelCreateWithoutRelationsInput:
    try:
        if isinstance(criteria, RankingCriteria):
            return Criteria_Type_ModelCreateInput(
                type=CriteriaTypeEnum.RANKING_CRITERIA,
                feedback_request_id=feedback_request_id,  # this is parent_id
                # options=cast(Json, json.dumps(criteria.options)),
                options=Json(json.dumps(criteria.options)),
            )
        elif isinstance(criteria, ScoreCriteria):
            return Criteria_Type_ModelCreateInput(
                type=CriteriaTypeEnum.SCORE,
                feedback_request_id=feedback_request_id,
                min=criteria.min,
                max=criteria.max,
                options=Json(json.dumps([])),
            )
        elif isinstance(criteria, MultiSelectCriteria):
            return Criteria_Type_ModelCreateInput(
                type=CriteriaTypeEnum.MULTI_SELECT,
                feedback_request_id=feedback_request_id,
                options=Json(json.dumps(criteria.options)),
            )
        elif isinstance(criteria, MultiScoreCriteria):
            return Criteria_Type_ModelCreateInput(
                type=CriteriaTypeEnum.MULTI_SCORE,
                feedback_request_id=feedback_request_id,
                options=Json(json.dumps(criteria.options)),
                min=criteria.min,
                max=criteria.max,
            )
        else:
            raise ValueError("Unknown criteria type")
    except Exception as e:
        raise ValueError(f"Failed to map criteria type to model {e}")


def map_criteria_type_model_to_criteria_type(
    model: Criteria_Type_Model,
) -> CriteriaType:
    try:
        if model.type == CriteriaTypeEnum.RANKING_CRITERIA:
            return RankingCriteria(
                options=json.loads(model.options) if model.options else []
            )
        elif model.type == CriteriaTypeEnum.SCORE:
            return ScoreCriteria(
                min=model.min if model.min is not None else 0.0,
                max=model.max if model.max is not None else 0.0,
            )
        elif model.type == CriteriaTypeEnum.MULTI_SELECT:
            return MultiSelectCriteria(
                options=json.loads(model.options) if model.options else []
            )
        elif model.type == CriteriaTypeEnum.MULTI_SCORE:
            return MultiScoreCriteria(
                options=json.loads(model.options) if model.options else [],
                min=model.min if model.min is not None else 0.0,
                max=model.max if model.max is not None else 0.0,
            )
        else:
            raise ValueError("Unknown criteria type")
    except Exception as e:
        logger.error(f"Failed to map criteria type model to criteria type: {e}")
        raise ValueError("Failed to map criteria type model to criteria type")


def map_completion_response_to_model(
    response: CompletionResponses, feedback_request_id: str
) -> Completion_Response_ModelCreateInput:
    try:
        result = Completion_Response_ModelCreateInput(
            completion_id=response.completion_id,
            model=response.model,
            completion=Json(json.dumps(response.completion)),
            rank_id=response.rank_id,
            score=response.score,
            feedback_request_id=feedback_request_id,
        )
        return result
    except Exception as e:
        raise ValueError(f"Failed to map completion response to model {e}")


def map_parent_feedback_request_to_model(
    request: FeedbackRequest,
) -> Feedback_Request_ModelCreateInput:
    try:
        if not request.axon or not request.axon.hotkey:
            raise ValueError("Validator Hotkey is required")

        expire_at = request.expire_at
        if expire_at is None or is_valid_expiry(expire_at) is not True:
            expire_at = set_expire_time(dojo.TASK_DEADLINE)

        result = Feedback_Request_ModelCreateInput(
            request_id=request.request_id,
            task_type=request.task_type,
            prompt=request.prompt,
            hotkey=request.axon.hotkey,
            expire_at=datetime.fromisoformat(expire_at),
        )

        return result
    except Exception as e:
        raise ValueError(f"Failed to map parent feedback request to model {e}")


def map_child_feedback_request_to_model(
    request: FeedbackRequest,
    parent_id: str,
) -> Feedback_Request_ModelCreateInput:
    try:
        if not request.axon or not request.axon.hotkey:
            raise ValueError("Miner Hotkey is required")

        if not parent_id:
            raise ValueError("Parent ID is required")

        if not request.dojo_task_id:
            raise ValueError("Dojo Task ID is required")

        expire_at = request.expire_at
        if expire_at is None or is_valid_expiry(expire_at) is not True:
            expire_at = set_expire_time(dojo.TASK_DEADLINE)

        result = Feedback_Request_ModelCreateInput(
            request_id=request.request_id,
            task_type=request.task_type,
            prompt=request.prompt,
            hotkey=request.axon.hotkey,
            expire_at=datetime.fromisoformat(expire_at),
            dojo_task_id=request.dojo_task_id,
            parent_id=parent_id,
        )

        return result
    except Exception as e:
        raise ValueError(f"Failed to map child feedback request to model {e}")


def map_feedback_request_model_to_feedback_request(
    model: Feedback_Request_Model, is_miner: bool = False
) -> FeedbackRequest:
    """Smaller function to map Feedback_Request_Model to FeedbackRequest

    Args:
        model (Feedback_Request_Model): Feedback_Request_Model from database.
        is_miner (bool, optional): If we're converting for a validator request or miner response.
        Defaults to False.

    Raises:
        ValueError: If failed to map.

    Returns:
        FeedbackRequest: FeedbackRequest object.
    """

    try:
        # Map criteria types
        criteria_types = [
            map_criteria_type_model_to_criteria_type(criteria)
            for criteria in model.criteria_types or []
        ]

        # Map completion responses
        completion_responses = [
            CompletionResponses(
                completion_id=completion.completion_id,
                model=completion.model,
                completion=json.loads(completion.completion),
                rank_id=completion.rank_id,
                score=completion.score,
            )
            for completion in model.completions or []
        ]

        ground_truth: dict[str, int] = {}

        if model.ground_truths:
            for gt in model.ground_truths:
                ground_truth[gt.obfuscated_model_id] = gt.rank_id

        if is_miner:
            # Create FeedbackRequest object
            feedback_request = FeedbackRequest(
                request_id=model.request_id,
                prompt=model.prompt,
                task_type=model.task_type,
                criteria_types=criteria_types,
                completion_responses=completion_responses,
                dojo_task_id=model.dojo_task_id,
                expire_at=model.expire_at.replace(microsecond=0, tzinfo=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                axon=bt.TerminalInfo(hotkey=model.hotkey),
            )
        else:
            feedback_request = FeedbackRequest(
                request_id=model.request_id,
                prompt=model.prompt,
                task_type=model.task_type,
                criteria_types=criteria_types,
                completion_responses=completion_responses,
                dojo_task_id=model.dojo_task_id,
                expire_at=model.expire_at.replace(microsecond=0, tzinfo=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                dendrite=bt.TerminalInfo(hotkey=model.hotkey),
                ground_truth=ground_truth,
            )

        return feedback_request
    except Exception as e:
        raise ValueError(
            f"Failed to map Feedback_Request_Model to FeedbackRequest: {e}"
        )
