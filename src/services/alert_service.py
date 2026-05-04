from src.config import settings
from src.models.retell import (
    ERROR_DISCONNECTION_REASONS,
    EVENT_COLORS,
    CallObject,
    WebhookEventType,
)
from src.models.slack import SlackAttachment, SlackPostMessageRequest
from src.providers.slack import SlackProvider
from src.utils.logger import logger


# Per-event title prefix for the Slack message header.
EVENT_TITLES: dict[WebhookEventType, str] = {
    WebhookEventType.CALL_STARTED: "📞 Call Started",
    WebhookEventType.CALL_ENDED: "📴 Call Ended",
    WebhookEventType.CALL_ANALYZED: "📋 Call Analyzed",
    WebhookEventType.TRANSCRIPT_UPDATED: "📝 Transcript Updated",
    WebhookEventType.TRANSFER_STARTED: "🔀 Transfer Started",
    WebhookEventType.TRANSFER_BRIDGED: "✅ Transfer Bridged",
    WebhookEventType.TRANSFER_CANCELLED: "❌ Transfer Cancelled",
    WebhookEventType.TRANSFER_ENDED: "🔚 Transfer Ended",
}


class AlertService:
    def __init__(self, slack: SlackProvider) -> None:
        self.slack = slack
        self.channel = settings.slack_alert_channel

    def _format_duration(self, ms: int | None) -> str:
        if ms is None:
            return "unknown"
        seconds = ms // 1000
        if seconds < 60:
            return f"{seconds} seconds"
        return f"{seconds // 60}m {seconds % 60}s"

    def _color_for(self, event: WebhookEventType, call: CallObject) -> str:
        # Errors always recolour red regardless of which event delivered them.
        if call.disconnection_reason in ERROR_DISCONNECTION_REASONS:
            return "#e01e5a"
        return EVENT_COLORS.get(event, "#1d9bd1")

    def _build_body(self, event: WebhookEventType, call: CallObject) -> str:
        # Identity is shown on every event; everything else is event-specific.
        lines = [
            f"*Call ID:* `{call.call_id}`",
            f"*Agent ID:* `{call.agent_id}`" if call.agent_id else None,
        ]
        if call.from_number or call.to_number:
            lines.append(f"*From:* {call.from_number or '?'}  →  *To:* {call.to_number or '?'}")

        if event == WebhookEventType.CALL_STARTED:
            lines.append(f"*Status:* {call.call_status.value if call.call_status else 'unknown'}")

        elif event == WebhookEventType.CALL_ENDED:
            lines.append(f"*Status:* {call.call_status.value if call.call_status else 'unknown'}")
            lines.append(f"*Duration:* {self._format_duration(call.duration_ms)}")
            if call.disconnection_reason:
                lines.append(f"*Disconnection Reason:* `{call.disconnection_reason.value}`")

        elif event == WebhookEventType.CALL_ANALYZED:
            lines.append(f"*Duration:* {self._format_duration(call.duration_ms)}")
            if call.disconnection_reason:
                lines.append(f"*Disconnection Reason:* `{call.disconnection_reason.value}`")
            if call.call_analysis:
                if call.call_analysis.user_sentiment:
                    lines.append(f"*Sentiment:* {call.call_analysis.user_sentiment}")
                if call.call_analysis.call_successful is not None:
                    lines.append(f"*Successful:* {call.call_analysis.call_successful}")
                if call.call_analysis.call_summary:
                    lines.append(f"\n*Summary:*\n{call.call_analysis.call_summary}")
            transcript = call.transcript or "_No transcript available_"
            lines.append(f"\n*Transcript:*\n{transcript}")

        elif event == WebhookEventType.TRANSCRIPT_UPDATED:
            transcript = call.transcript or "_No transcript yet_"
            # Cap mid-call transcript snapshots so Slack doesn't truncate awkwardly.
            if len(transcript) > 1500:
                transcript = transcript[-1500:]
                transcript = "…" + transcript[transcript.find("\n") + 1 :]
            lines.append(f"\n*Transcript (latest):*\n{transcript}")

        elif event in (
            WebhookEventType.TRANSFER_STARTED,
            WebhookEventType.TRANSFER_BRIDGED,
            WebhookEventType.TRANSFER_CANCELLED,
            WebhookEventType.TRANSFER_ENDED,
        ):
            if call.transfer_destination:
                lines.append(f"*Transfer Destination:* {call.transfer_destination}")
            if call.duration_ms is not None:
                lines.append(f"*Duration:* {self._format_duration(call.duration_ms)}")

        return "\n".join(line for line in lines if line)

    def _build_attachment(
        self, event: WebhookEventType, call: CallObject
    ) -> SlackAttachment:
        return SlackAttachment(
            text=self._build_body(event, call),
            fallback=f"{EVENT_TITLES.get(event, event.value)} — {call.call_id}",
            color=self._color_for(event, call),
        )

    async def send_event_alert(self, event: WebhookEventType, call: CallObject) -> None:
        title = EVENT_TITLES.get(event, event.value)
        message = SlackPostMessageRequest(
            channel=self.channel,
            text=f"{title} — `{call.call_id}`",
            attachments=[self._build_attachment(event, call)],
        )
        await self.slack.post_message(message)

    # Used by /webhook/retell — every event is alerted; we never skip.
    async def alert_for_event(self, event: WebhookEventType, call: CallObject) -> bool:
        try:
            await self.send_event_alert(event, call)
            return True
        except Exception as e:
            logger.error(
                f"Failed to send Slack alert | call_id={call.call_id} event={event} error={e!r}"
            )
            return False
