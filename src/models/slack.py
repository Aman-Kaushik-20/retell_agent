from typing import Optional
from pydantic import BaseModel, ConfigDict


class SlackAction(BaseModel):
    name: str
    text: str
    type: str
    data_source: Optional[str] = None


class SlackAttachment(BaseModel):
    text: Optional[str] = None
    fallback: Optional[str] = None
    color: Optional[str] = None
    attachment_type: Optional[str] = None
    callback_id: Optional[str] = None
    actions: Optional[list[SlackAction]] = None

# Slack Request to send to the POST request for messages
class SlackPostMessageRequest(BaseModel):
    channel: str
    text: str
    attachments: Optional[list[SlackAttachment]] = None

# Slack Response of the POST request for messages
class SlackResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool
    error: Optional[str] = None
    warning: Optional[str] = None
