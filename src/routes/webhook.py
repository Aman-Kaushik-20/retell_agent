from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.models.retell import WebhookEvent
from src.utils.logger import logger
from src.utils.openapi import (
    WEBHOOK_DESCRIPTION,
    WEBHOOK_OPENAPI_EXTRA,
    WEBHOOK_RESPONSES,
    WEBHOOK_SUMMARY,
)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# Retell calls this endpoint for every subscribed event. Each event becomes
# its own Slack alert — no skip filter.
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
        # Always 200 — a parser failure must not trigger Retell's retry storm.
        logger.error(f"Retell webhook payload could not be parsed | error={e!r} body={raw[:500]!r}")
        return JSONResponse({"received": True})

    logger.info(
        f"Retell webhook received | event={payload.event.value} "
        f"call_id={payload.call.call_id} status={payload.call.call_status}"
    )
    await request.app.state.alert_service.alert_for_event(payload.event, payload.call)
    return JSONResponse({"received": True})
