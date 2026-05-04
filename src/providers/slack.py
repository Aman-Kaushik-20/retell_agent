import httpx

from src.config import settings
from src.models.retell import CallObject, WebhookEventType
from src.models.slack import SlackResponse
from src.providers._attachment import build_message
from src.utils.logger import logger


# Slack notifier — owns its HTTP client, builds the message, posts to chat.postMessage.
class SlackProvider:
    name = "slack"

    def __init__(self) -> None:
        self.base_url = settings.slack_base_url.rstrip("/")
        self.token = settings.slack_bot_token
        self.channel = settings.slack_alert_channel
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def send(self, event: WebhookEventType, call: CallObject) -> None:
        message = build_message(self.channel, event, call)
        logger.info(f"Slack post | call_id={call.call_id} event={event.value}")

        response = await self.client.post(
            "/chat.postMessage", json=message.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        # Slack always returns HTTP 200 — real errors come back as `ok: false` in the body.
        result = SlackResponse.model_validate(response.json())
        if not result.ok:
            logger.error(
                f"Slack post rejected | call_id={call.call_id} channel={self.channel} "
                f"error={result.error}"
            )
            raise RuntimeError(f"Slack API error: {result.error}")
