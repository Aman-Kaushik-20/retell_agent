from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── Enums ────────────────────────────────────────────────────────────────────

# All possible call states from Retell. Far simpler than Bolna's 15-state enum.
class CallStatus(str, Enum):
    REGISTERED = "registered"
    NOT_CONNECTED = "not_connected"
    ONGOING = "ongoing"
    ENDED = "ended"
    ERROR = "error"


class CallType(str, Enum):
    PHONE_CALL = "phone_call"
    WEB_CALL = "web_call"


class Direction(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


# Every webhook event Retell sends. Each one triggers a Slack alert.
class WebhookEventType(str, Enum):
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"
    CALL_ANALYZED = "call_analyzed"
    TRANSCRIPT_UPDATED = "transcript_updated"
    TRANSFER_STARTED = "transfer_started"
    TRANSFER_BRIDGED = "transfer_bridged"
    TRANSFER_CANCELLED = "transfer_cancelled"
    TRANSFER_ENDED = "transfer_ended"


# Retell's full disconnection_reason enum (37 values). We don't filter on these,
# but we colour-code Slack alerts with them.
class DisconnectionReason(str, Enum):
    USER_HANGUP = "user_hangup"
    AGENT_HANGUP = "agent_hangup"
    CALL_TRANSFER = "call_transfer"
    VOICEMAIL_REACHED = "voicemail_reached"
    IVR_REACHED = "ivr_reached"
    INACTIVITY = "inactivity"
    MAX_DURATION_REACHED = "max_duration_reached"
    CONCURRENCY_LIMIT_REACHED = "concurrency_limit_reached"
    NO_VALID_PAYMENT = "no_valid_payment"
    SCAM_DETECTED = "scam_detected"
    DIAL_BUSY = "dial_busy"
    DIAL_FAILED = "dial_failed"
    DIAL_NO_ANSWER = "dial_no_answer"
    INVALID_DESTINATION = "invalid_destination"
    TELEPHONY_PROVIDER_PERMISSION_DENIED = "telephony_provider_permission_denied"
    TELEPHONY_PROVIDER_UNAVAILABLE = "telephony_provider_unavailable"
    SIP_ROUTING_ERROR = "sip_routing_error"
    MARKED_AS_SPAM = "marked_as_spam"
    USER_DECLINED = "user_declined"
    ERROR_LLM_WEBSOCKET_OPEN = "error_llm_websocket_open"
    ERROR_LLM_WEBSOCKET_LOST_CONNECTION = "error_llm_websocket_lost_connection"
    ERROR_LLM_WEBSOCKET_RUNTIME = "error_llm_websocket_runtime"
    ERROR_LLM_WEBSOCKET_CORRUPT_PAYLOAD = "error_llm_websocket_corrupt_payload"
    ERROR_NO_AUDIO_RECEIVED = "error_no_audio_received"
    ERROR_ASR = "error_asr"
    ERROR_RETELL = "error_retell"
    ERROR_UNKNOWN = "error_unknown"
    ERROR_USER_NOT_JOINED = "error_user_not_joined"
    REGISTERED_CALL_TIMEOUT = "registered_call_timeout"
    TRANSFER_BRIDGED = "transfer_bridged"
    TRANSFER_CANCELLED = "transfer_cancelled"
    MANUAL_STOPPED = "manual_stopped"


# Disconnection reasons that look like errors — used to recolour alerts red.
ERROR_DISCONNECTION_REASONS = {
    DisconnectionReason.ERROR_LLM_WEBSOCKET_OPEN,
    DisconnectionReason.ERROR_LLM_WEBSOCKET_LOST_CONNECTION,
    DisconnectionReason.ERROR_LLM_WEBSOCKET_RUNTIME,
    DisconnectionReason.ERROR_LLM_WEBSOCKET_CORRUPT_PAYLOAD,
    DisconnectionReason.ERROR_NO_AUDIO_RECEIVED,
    DisconnectionReason.ERROR_ASR,
    DisconnectionReason.ERROR_RETELL,
    DisconnectionReason.ERROR_UNKNOWN,
    DisconnectionReason.ERROR_USER_NOT_JOINED,
    DisconnectionReason.SIP_ROUTING_ERROR,
    DisconnectionReason.TELEPHONY_PROVIDER_PERMISSION_DENIED,
    DisconnectionReason.TELEPHONY_PROVIDER_UNAVAILABLE,
    DisconnectionReason.DIAL_FAILED,
    DisconnectionReason.INVALID_DESTINATION,
}


# Slack attachment colour per webhook event. Errors override to red downstream.
EVENT_COLORS: dict[WebhookEventType, str] = {
    WebhookEventType.CALL_STARTED: "#1d9bd1",
    WebhookEventType.CALL_ENDED: "#ecb22e",
    WebhookEventType.CALL_ANALYZED: "#2eb67d",
    WebhookEventType.TRANSCRIPT_UPDATED: "#919191",
    WebhookEventType.TRANSFER_STARTED: "#ec2ed6",
    WebhookEventType.TRANSFER_BRIDGED: "#2eb67d",
    WebhookEventType.TRANSFER_CANCELLED: "#e01e5a",
    WebhookEventType.TRANSFER_ENDED: "#ecb22e",
}


# ─── Request: POST /calls ─────────────────────────────────────────────────────

# Schema for placing an outbound call. Mirrors Retell's /v2/create-phone-call body.
# `from_number` is optional at our boundary because we fall back to the env default.
class CallRequestModel(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "to_number": "+91xxxxxxxxxx",
                    "override_agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
                }
            ]
        }
    )

    to_number: str
    from_number: Optional[str] = None
    override_agent_id: Optional[str] = None
    override_agent_version: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None
    retell_llm_dynamic_variables: Optional[dict[str, str]] = None
    custom_sip_headers: Optional[dict[str, str]] = None


# ─── Response: POST /calls ────────────────────────────────────────────────────

# Slim response — only the fields a caller needs to follow up on the call.
class CallResponseModel(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "call_id": "119c3f8e47135a29e65947eeb34cf12d",
                    "call_status": "registered",
                    "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
                    "from_number": "+14157774444",
                    "to_number": "++91xxxxxxxxxx",
                }
            ]
        }
    )

    call_id: str
    call_status: CallStatus
    agent_id: Optional[str] = None
    agent_version: Optional[int] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    direction: Optional[Direction] = None


# ─── Nested objects on a full call ────────────────────────────────────────────


class CallAnalysis(BaseModel):
    model_config = ConfigDict(extra="allow")

    call_summary: Optional[str] = None
    in_voicemail: Optional[bool] = None
    user_sentiment: Optional[str] = None  # "Negative" | "Positive" | "Neutral" | "Unknown"
    call_successful: Optional[bool] = None
    custom_analysis_data: Optional[dict[str, Any]] = None


class TelephonyIdentifier(BaseModel):
    model_config = ConfigDict(extra="allow")

    twilio_call_sid: Optional[str] = None


class CallCost(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_duration_seconds: Optional[float] = None
    total_duration_unit_price: Optional[float] = None
    combined_cost: Optional[float] = None
    product_costs: Optional[list[dict[str, Any]]] = None


# Full V2CallResponse. extra="allow" since field population varies wildly per
# event type and Retell adds new fields over time.
class CallObject(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "call_id": "119c3f8e47135a29e65947eeb34cf12d",
                    "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
                    "agent_version": 1,
                    "call_type": "phone_call",
                    "call_status": "ended",
                    "from_number": "+14157774444",
                    "to_number": "++91xxxxxxxxxx",
                    "direction": "outbound",
                    "start_timestamp": 1747000000000,
                    "end_timestamp": 1747000042000,
                    "duration_ms": 42000,
                    "disconnection_reason": "user_hangup",
                    "transcript": "Agent: Hi! ...\nUser: Hello.\n...",
                    "call_analysis": {
                        "call_summary": "User asked about the demo and said they would call back.",
                        "user_sentiment": "Positive",
                        "call_successful": True,
                    },
                }
            ]
        },
    )

    # Identity / config
    call_id: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_version: Optional[int] = None
    call_type: Optional[CallType] = None
    call_status: Optional[CallStatus] = None

    # Phone call shape
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    direction: Optional[Direction] = None
    telephony_identifier: Optional[TelephonyIdentifier] = None
    custom_sip_headers: Optional[dict[str, str]] = None

    # Caller-supplied passthrough
    metadata: Optional[dict[str, Any]] = None
    retell_llm_dynamic_variables: Optional[dict[str, str]] = None
    collected_dynamic_variables: Optional[dict[str, Any]] = None

    # Timing (populated as call progresses)
    start_timestamp: Optional[int] = None
    end_timestamp: Optional[int] = None
    transfer_end_timestamp: Optional[int] = None
    duration_ms: Optional[int] = None

    # Post-call (populated on call_ended / call_analyzed)
    transcript: Optional[str] = None
    transcript_object: Optional[list[dict[str, Any]]] = None
    transcript_with_tool_calls: Optional[list[dict[str, Any]]] = None
    recording_url: Optional[str] = None
    public_log_url: Optional[str] = None
    disconnection_reason: Optional[DisconnectionReason] = None
    transfer_destination: Optional[str] = None
    call_analysis: Optional[CallAnalysis] = None
    call_cost: Optional[CallCost] = None


# ─── Webhook envelope ─────────────────────────────────────────────────────────

# Retell wraps every webhook payload in {"event": "...", "call": {...}}.
class WebhookEvent(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "event": "call_ended",
                    "call": {
                        "call_id": "119c3f8e47135a29e65947eeb34cf12d",
                        "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
                        "call_status": "ended",
                        "duration_ms": 42000,
                        "disconnection_reason": "user_hangup",
                        "transcript": "Agent: Hi ...\nUser: Hello.\n...",
                    },
                }
            ]
        },
    )

    event: WebhookEventType
    call: CallObject
    transfer_destination: Optional[str] = Field(default=None)


# ─── Error response (Retell shape) ────────────────────────────────────────────


class RetellErrorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    error_code: Optional[str] = None
    error_message: Optional[str] = None
