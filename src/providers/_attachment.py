"""Shared Slack-shaped attachment builder.

Slack and Mattermost both consume this exact JSON shape, so the formatter
lives here and is imported by both providers.
"""

from src.models.retell import (
    ERROR_DISCONNECTION_REASONS,
    EVENT_COLORS,
    CallObject,
    WebhookEventType,
)
from src.models.slack import SlackAttachment, SlackPostMessageRequest


# Per-event title prefix.
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


def _format_duration(ms: int | None) -> str:
    if ms is None:
        return "unknown"
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds} seconds"
    return f"{seconds // 60}m {seconds % 60}s"


def _color_for(event: WebhookEventType, call: CallObject) -> str:
    # Errors override to red regardless of which event delivered them.
    if call.disconnection_reason in ERROR_DISCONNECTION_REASONS:
        return "#e01e5a"
    return EVENT_COLORS.get(event, "#1d9bd1")


def build_body(event: WebhookEventType, call: CallObject) -> str:
    lines: list[str | None] = [
        f"*Call ID:* `{call.call_id}`",
        f"*Agent ID:* `{call.agent_id}`" if call.agent_id else None,
    ]
    if call.from_number or call.to_number:
        lines.append(f"*From:* {call.from_number or '?'}  →  *To:* {call.to_number or '?'}")

    if event == WebhookEventType.CALL_STARTED:
        lines.append(f"*Status:* {call.call_status.value if call.call_status else 'unknown'}")

    elif event == WebhookEventType.CALL_ENDED:
        lines.append(f"*Status:* {call.call_status.value if call.call_status else 'unknown'}")
        lines.append(f"*Duration:* {_format_duration(call.duration_ms)}")
        if call.disconnection_reason:
            lines.append(f"*Disconnection Reason:* `{call.disconnection_reason.value}`")

    elif event == WebhookEventType.CALL_ANALYZED:
        lines.append(f"*Duration:* {_format_duration(call.duration_ms)}")
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
        # Cap mid-call snapshots so Slack/Mattermost don't truncate awkwardly.
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
            lines.append(f"*Duration:* {_format_duration(call.duration_ms)}")

    return "\n".join(line for line in lines if line)


def build_message(
    channel: str, event: WebhookEventType, call: CallObject
) -> SlackPostMessageRequest:
    title = EVENT_TITLES.get(event, event.value)
    return SlackPostMessageRequest(
        channel=channel,
        text=f"{title} — `{call.call_id}`",
        attachments=[
            SlackAttachment(
                text=build_body(event, call),
                fallback=f"{title} — {call.call_id}",
                color=_color_for(event, call),
            )
        ],
    )


def title_for(event: WebhookEventType) -> str:
    return EVENT_TITLES.get(event, event.value)
