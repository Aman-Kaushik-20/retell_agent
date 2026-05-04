import httpx

from src.config import settings
from src.models.retell import CallObject, WebhookEventType
from src.providers._attachment import _format_duration, title_for
from src.utils.logger import logger


# ClickUp comments are plain text (no rich shape supported on this endpoint),
# so we flatten the same fields Slack/Discord show into a multi-line string.
def _build_comment(event: WebhookEventType, call: CallObject) -> str:
    lines = [f"{title_for(event)} — {call.call_id}", ""]

    if call.agent_id:
        lines.append(f"Agent: {call.agent_id}")
    if call.from_number or call.to_number:
        lines.append(f"From → To: {call.from_number or '?'} → {call.to_number or '?'}")
    if call.call_status:
        lines.append(f"Status: {call.call_status.value}")
    if call.duration_ms is not None and event != WebhookEventType.CALL_STARTED:
        lines.append(f"Duration: {_format_duration(call.duration_ms)}")
    if call.disconnection_reason:
        lines.append(f"Disconnection Reason: {call.disconnection_reason.value}")
    if call.transfer_destination:
        lines.append(f"Transfer Destination: {call.transfer_destination}")

    if event == WebhookEventType.CALL_ANALYZED and call.call_analysis:
        if call.call_analysis.user_sentiment:
            lines.append(f"Sentiment: {call.call_analysis.user_sentiment}")
        if call.call_analysis.call_successful is not None:
            lines.append(f"Successful: {call.call_analysis.call_successful}")
        if call.call_analysis.call_summary:
            lines.extend(["", "Summary:", call.call_analysis.call_summary])

    if event in (WebhookEventType.CALL_ANALYZED, WebhookEventType.TRANSCRIPT_UPDATED):
        transcript = call.transcript
        if event == WebhookEventType.TRANSCRIPT_UPDATED and transcript and len(transcript) > 1500:
            transcript = transcript[-1500:]
            transcript = "…" + transcript[transcript.find("\n") + 1 :]
        if transcript:
            lines.extend(["", "Transcript:", transcript])

    return "\n".join(lines)


# ClickUp notifier — appends a comment on the configured task for every event.
class ClickUpProvider:
    name = "clickup"
    BASE_URL = "https://api.clickup.com/api/v2"

    def __init__(self) -> None:
        self.task_id = settings.clickup_task_id
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(15.0, connect=5.0),
            # ClickUp uses the raw token in Authorization, not "Bearer ...".
            headers={
                "Authorization": settings.clickup_api_token,
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def send(self, event: WebhookEventType, call: CallObject) -> None:
        payload = {
            "comment_text": _build_comment(event, call),
            "notify_all": False,
        }
        logger.info(f"ClickUp post | call_id={call.call_id} event={event.value} task={self.task_id}")
        response = await self.client.post(f"/task/{self.task_id}/comment", json=payload)
        response.raise_for_status()
