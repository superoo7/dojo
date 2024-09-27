import json
from typing import List

from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, UploadFile, responses
from fastapi.encoders import jsonable_encoder
from loguru import logger
from pydantic.error_wrappers import ValidationError

from commons.cache import RedisCache
from commons.objects import ObjectManager
from template.protocol import FeedbackRequest

load_dotenv()


threed_gen_router = APIRouter(prefix="/api/threed_gen")


cache = RedisCache()


@threed_gen_router.post("/")
async def create_3d_gen_task(
    files: List[UploadFile] = File(None),
    task_data: str = Form(...),
):
    try:
        request_data = json.loads(task_data)
        if not request_data:
            logger.error("Empty request body")
            return responses.JSONResponse(
                status_code=400, content={"message": "Request body is empty"}
            )

        for response in request_data["responses"]:
            if (
                isinstance(response["completion"], dict)
                and "filename" in response["completion"]
            ):
                response["completion"] = {
                    "filename": response["completion"]["filename"]
                }

        logger.info("Received task data from external user")
        logger.debug(f"Task data: {request_data}")
        request_data["files"] = files if files else []
        try:
            task_data = FeedbackRequest.model_validate(request_data)
        except ValidationError as ve:
            logger.error(f"Validation error: {ve}")
            return responses.JSONResponse(
                status_code=400, content={"message": f"Invalid request data: {str(ve)}"}
            )

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return responses.JSONResponse(
            status_code=400, content={"message": "Invalid JSON in request body"}
        )

    except (KeyError, ValidationError):
        logger.error("Invalid data sent by external user")
        return responses.JSONResponse(
            status_code=400, content={"message": "Invalid request data"}
        )
    except Exception as e:
        logger.exception(f"Encountered exception: {e}")
        return responses.JSONResponse(
            status_code=500, content={"message": "Internal server error"}
        )

    try:
        validator = ObjectManager.get_validator()
        response = await validator.send_request(task_data, external_user=True)
        response_json = jsonable_encoder(response)
        return responses.JSONResponse(content=response_json)
    except Exception as e:
        logger.exception(f"Encountered exception: {e}")
        return responses.JSONResponse(
            status_code=500, content={"message": "Internal server error"}
        )
