import asyncio

from src.models.retell import CallObject, WebhookEventType
from src.utils.logger import logger


# Fan a single (event, call) out to every notifier concurrently.
# return_exceptions=True so one provider failing doesn't kill the others.
async def fanout(notifiers, event: WebhookEventType, call: CallObject) -> dict[str, str]:
    if not notifiers:
        return {}

    results = await asyncio.gather(
        *(n.send(event, call) for n in notifiers),
        return_exceptions=True,
    )

    delivered = {}
    for n, r in zip(notifiers, results):
        if isinstance(r, Exception):
            logger.error(
                f"Notifier failed | provider={n.name} call_id={call.call_id} "
                f"event={event.value} error={r!r}"
            )
            delivered[n.name] = f"error: {type(r).__name__}: {r}"
        else:
            delivered[n.name] = "ok"
    return delivered
