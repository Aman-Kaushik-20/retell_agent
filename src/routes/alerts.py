import httpx
from fastapi import APIRouter, HTTPException, Request, status

from src.models.retell import WebhookEventType
from src.services.notifier import fanout
from src.utils.logger import logger
from src.utils.openapi import ALERT_DESCRIPTION, ALERT_RESPONSES, ALERT_SUMMARY

router = APIRouter(prefix="/alerts", tags=["alerts"])


# Manual back-fill: fetch the call from Retell, then fan a `call_analyzed`-shaped
# notification out to every enabled notifier.
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

    # call_analyzed is the richest format (transcript + summary + sentiment) — best for backfills.
    delivered = await fanout(request.app.state.notifiers, WebhookEventType.CALL_ANALYZED, call)

    return {
        "sent": True,
        "call_id": call.call_id,
        "call_status": call.call_status.value if call.call_status else None,
        "delivered": delivered,
    }
