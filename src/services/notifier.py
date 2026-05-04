import asyncio

from src.models.retell import CallObject, WebhookEventType


# Fan a single (event, call) out to every notifier concurrently.
# return_exceptions=True so one provider failing doesn't kill the others.
async def fanout(notifiers, event: WebhookEventType, call: CallObject) -> dict[str, str]:
    if not notifiers:
        return {}

    results = await asyncio.gather(
        *(n.send(event, call) for n in notifiers),
        return_exceptions=True,
    )
    return {
        n.name: "ok" if not isinstance(r, Exception) else f"error: {type(r).__name__}: {r}"
        for n, r in zip(notifiers, results)
    }
