from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.models.retell import WebhookEvent
from src.services.notifier import fanout
from src.utils.logger import logger
from src.utils.openapi import (
    WEBHOOK_DESCRIPTION,
    WEBHOOK_OPENAPI_EXTRA,
    WEBHOOK_RESPONSES,
    WEBHOOK_SUMMARY,
)

router = APIRouter(prefix="/webhook", tags=["webhook"])


# Retell calls this for every subscribed event. We fan out to every enabled
# notifier (Slack / Discord / Mattermost / ClickUp). Always return 200 — a
# non-2xx triggers Retell's retry storm.
@router.post(
    "/retell",
    status_code=status.HTTP_200_OK,
    summary=WEBHOOK_SUMMARY,
    description=WEBHOOK_DESCRIPTION,
    openapi_extra=WEBHOOK_OPENAPI_EXTRA,
    responses=WEBHOOK_RESPONSES,
)
async def retell_webhook(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        payload = WebhookEvent.model_validate_json(raw)
    except Exception as e:
        logger.error(f"Retell webhook payload could not be parsed | error={e!r} body={raw[:500]!r}")
        return JSONResponse({"received": True})

    logger.info(
        f"Retell webhook received | event={payload.event.value} "
        f"call_id={payload.call.call_id} status={payload.call.call_status}"
    )
    delivered = await fanout(request.app.state.notifiers, payload.event, payload.call)
    return JSONResponse({"received": True, "delivered": delivered})
