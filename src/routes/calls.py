import httpx
from fastapi import APIRouter, Body, HTTPException, Request, status

from src.models.retell import CallObject, CallRequestModel, CallResponseModel
from src.utils.logger import logger
from src.utils.openapi import (
    CALL_REQUEST_EXAMPLES,
    GET_CALL_DESCRIPTION,
    GET_CALL_RESPONSES,
    GET_CALL_SUMMARY,
    MAKE_CALL_DESCRIPTION,
    MAKE_CALL_RESPONSES,
    MAKE_CALL_SUMMARY,
)

router = APIRouter(prefix="/calls", tags=["calls"])

# Forwards the request to Retell's `POST /v2/create-phone-call` and returns the registered `call_id`.
@router.post(
    "",
    response_model=CallResponseModel,
    summary=MAKE_CALL_SUMMARY,
    description=MAKE_CALL_DESCRIPTION,
    responses=MAKE_CALL_RESPONSES,
)
async def make_call(
    request: Request,
    payload: CallRequestModel = Body(..., openapi_examples=CALL_REQUEST_EXAMPLES),
) -> CallResponseModel:
    try:
        return await request.app.state.call_service.initiate_call(payload)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.HTTPError as e:
        logger.error(f"Retell transport error in make_call | error={e!r}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Retell upstream error")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Fetch a call's full record from Retell.
@router.get(
    "/{call_id}",
    response_model=CallObject,
    summary=GET_CALL_SUMMARY,
    description=GET_CALL_DESCRIPTION,
    responses=GET_CALL_RESPONSES,
)
async def get_call(call_id: str, request: Request) -> CallObject:
    try:
        return await request.app.state.call_service.get_call(call_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.HTTPError as e:
        logger.error(f"Retell transport error in get_call | error={e!r}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Retell upstream error")
