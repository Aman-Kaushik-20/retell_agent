import httpx

from src.config import settings
from src.models.retell import CallObject, WebhookEventType
from src.providers._attachment import build_message
from src.utils.logger import logger


# Mattermost notifier — incoming-webhook URL is Slack-compatible.
# We reuse the Slack message builder verbatim; Mattermost's incoming webhook
# endpoint accepts the same `{text, attachments}` JSON shape.
class MattermostProvider:
    name = "mattermost"

    def __init__(self) -> None:
        self.webhook_url = settings.mattermost_webhook_url
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "retell-agent/0.3",
            },
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def send(self, event: WebhookEventType, call: CallObject) -> None:
        # Mattermost ignores `channel` for webhooks bound to a specific channel,
        # but the field is required by the model — pass empty.
        message = build_message("", event, call)
        payload = message.model_dump(exclude_none=True)
        # Drop the empty channel key so we don't accidentally override the
        # webhook's bound channel on Mattermost servers that respect it.
        payload.pop("channel", None)

        logger.info(f"Mattermost post | call_id={call.call_id} event={event.value}")
        response = await self.client.post(self.webhook_url, json=payload)
        if response.status_code >= 400:
            logger.error(
                f"Mattermost post failed | call_id={call.call_id} "
                f"status={response.status_code} body={response.text[:500]}"
            )
        response.raise_for_status()
