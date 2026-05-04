import httpx

from src.config import settings
from src.models.slack import SlackPostMessageRequest, SlackResponse
from src.utils.logger import logger

# Provider Class for Slack - Just for Sending Message to a Slack Channel
class SlackProvider:
    def __init__(self) -> None:
        self.slack_base_url = settings.slack_base_url.rstrip("/")
        self.slack_bot_token = settings.slack_bot_token
        self.client = httpx.AsyncClient(
            base_url=self.slack_base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={
                "Authorization": f"Bearer {self.slack_bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
        ) # Initialize client before-hand so runtime latency is low

    async def close(self) -> None:
        await self.client.aclose()

    async def post_message(self, message: SlackPostMessageRequest) -> SlackResponse:
        logger.info(f"Posting Slack message | channel={message.channel}")

        try:
            response = await self.client.post(
                "/chat.postMessage",
                json=message.model_dump(exclude_none=True),
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Slack chat.postMessage transport error | channel={message.channel} error={e!r}")
            raise

        result = SlackResponse.model_validate(response.json())
        if not result.ok:
            logger.error(f"Slack chat.postMessage rejected | channel={message.channel} error={result.error}")
            raise RuntimeError(f"Slack API error: {result.error}")

        logger.info(f"Slack message posted | channel={message.channel} ts={result.ts}")
        return result
