import httpx
from fastapi import APIRouter, HTTPException, Request, status

from src.models.retell import WebhookEventType
from src.utils.logger import logger
from src.utils.openapi import ALERT_DESCRIPTION, ALERT_RESPONSES, ALERT_SUMMARY

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Fetches the call from Retell, then posts a `call_analyzed`-shaped Slack alert.
@router.post(
    "/{call_id}",
    summary=ALERT_SUMMARY,
    description=ALERT_DESCRIPTION,
    responses=ALERT_RESPONSES,
)
async def alert_for_call(call_id: str, request: Request) -> dict[str, object]:
    try:
        call = await request.app.state.call_service.get_call(call_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.HTTPError as e:
        logger.error(f"Retell transport error in manual alert | call_id={call_id} error={e!r}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Retell upstream error")

    try:
        # Manual alerts always render as call_analyzed — that's the richest format
        # (transcript + summary if present), and matches what an operator wants for backfills.
        await request.app.state.alert_service.send_event_alert(
            WebhookEventType.CALL_ANALYZED, call
        )
    except Exception as e:
        logger.error(f"Slack send failed in manual alert | call_id={call_id} error={e!r}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Slack send failed: {e}")

    return {
        "sent": True,
        "call_id": call.call_id,
        "call_status": call.call_status.value if call.call_status else None,
    }
