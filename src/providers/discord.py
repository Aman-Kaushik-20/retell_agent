import httpx

from src.config import settings
from src.models.retell import (
    ERROR_DISCONNECTION_REASONS,
    EVENT_COLORS,
    CallObject,
    WebhookEventType,
)
from src.providers._attachment import _format_duration, title_for
from src.utils.logger import logger


# Convert Slack-style "#rrggbb" colour to Discord embed integer.
def _hex_to_int(color: str) -> int:
    return int(color.lstrip("#"), 16)


def _color_for(event: WebhookEventType, call: CallObject) -> int:
    if call.disconnection_reason in ERROR_DISCONNECTION_REASONS:
        return _hex_to_int("#e01e5a")
    return _hex_to_int(EVENT_COLORS.get(event, "#1d9bd1"))


def _build_embed(event: WebhookEventType, call: CallObject) -> dict:
    fields: list[dict] = []
    if call.agent_id:
        fields.append({"name": "Agent ID", "value": f"`{call.agent_id}`", "inline": True})
    if call.from_number or call.to_number:
        fields.append(
            {
                "name": "From → To",
                "value": f"{call.from_number or '?'} → {call.to_number or '?'}",
                "inline": True,
            }
        )
    if call.call_status:
        fields.append({"name": "Status", "value": call.call_status.value, "inline": True})
    if call.duration_ms is not None and event != WebhookEventType.CALL_STARTED:
        fields.append(
            {"name": "Duration", "value": _format_duration(call.duration_ms), "inline": True}
        )
    if call.disconnection_reason:
        fields.append(
            {
                "name": "Disconnection Reason",
                "value": f"`{call.disconnection_reason.value}`",
                "inline": True,
            }
        )
    if call.transfer_destination:
        fields.append(
            {"name": "Transfer Destination", "value": call.transfer_destination, "inline": True}
        )

    description_parts: list[str] = []
    if event == WebhookEventType.CALL_ANALYZED and call.call_analysis:
        if call.call_analysis.user_sentiment:
            fields.append(
                {"name": "Sentiment", "value": call.call_analysis.user_sentiment, "inline": True}
            )
        if call.call_analysis.call_successful is not None:
            fields.append(
                {
                    "name": "Successful",
                    "value": str(call.call_analysis.call_successful),
                    "inline": True,
                }
            )
        if call.call_analysis.call_summary:
            description_parts.append(f"**Summary**\n{call.call_analysis.call_summary}")

    if event in (WebhookEventType.CALL_ANALYZED, WebhookEventType.TRANSCRIPT_UPDATED):
        transcript = call.transcript
        if event == WebhookEventType.TRANSCRIPT_UPDATED and transcript and len(transcript) > 1500:
            transcript = transcript[-1500:]
            transcript = "…" + transcript[transcript.find("\n") + 1 :]
        if transcript:
            # Discord embed description max is 4096 chars; cap for safety.
            transcript = transcript[:3500]
            description_parts.append(f"**Transcript**\n```\n{transcript}\n```")

    return {
        "title": f"{title_for(event)} — {call.call_id}",
        "color": _color_for(event, call),
        "fields": fields,
        "description": "\n\n".join(description_parts) if description_parts else None,
    }


# Discord notifier — webhook URL is the only credential. POSTs an `embeds` array.
class DiscordProvider:
    name = "discord"

    def __init__(self) -> None:
        self.webhook_url = settings.discord_webhook_url
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            # Identifiable User-Agent — Discord's edge (Cloudflare) flags the
            # default python-httpx UA from cloud IPs as bot traffic, which
            # surfaces as HTML 429s with multi-minute retry_after.
            headers={
                "Content-Type": "application/json",
                "User-Agent": "retell-agent/0.3 (+https://retell-agent-6ark.onrender.com)",
            },
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def send(self, event: WebhookEventType, call: CallObject) -> None:
        embed = _build_embed(event, call)
        # Discord rejects null fields; strip them out.
        embed = {k: v for k, v in embed.items() if v is not None}
        payload = {"embeds": [embed]}

        logger.info(f"Discord post | call_id={call.call_id} event={event.value}")
        response = await self.client.post(self.webhook_url, json=payload)
        if response.status_code >= 400:
            # Surface Discord's response (rate-limit headers + JSON error body)
            # so the server log makes the cause obvious.
            retry_after = response.headers.get("x-ratelimit-reset-after") or response.headers.get("retry-after")
            logger.error(
                f"Discord post failed | call_id={call.call_id} status={response.status_code} "
                f"retry_after={retry_after} body={response.text[:500]}"
            )
        response.raise_for_status()
