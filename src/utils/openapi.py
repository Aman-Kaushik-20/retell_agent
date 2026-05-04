"""OpenAPI metadata: app description, tag info, route summaries, and request examples.

Kept separate from route files so the handlers stay short and readable.
"""

API_DESCRIPTION = """
Backend integration that:

1. Initiates outbound voice calls via the **Retell AI** API.
2. Receives Retell's webhook events and **fans them out to every configured notifier**:
   Slack, Discord, Mattermost, and ClickUp (task comments).
3. Exposes a manual alert endpoint so a notification can be triggered for any past `call_id`.

A notifier is enabled when its env vars are set; missing vars silently disable that provider.
`/health` returns the live list of enabled notifiers.

**Tags**

- `calls` — initiate / fetch calls on Retell.
- `alerts` — manually fan out a notification for an existing call.
- `webhook` — Retell webhook receiver (called by Retell, not by you).
- `health` — liveness probe + enabled-notifier inventory.
"""

OPENAPI_TAGS = [
    {"name": "calls", "description": "Initiate outbound calls and fetch their full record from Retell."},
    {"name": "alerts", "description": "Manually fan out a notification for a call_id across all enabled notifiers."},
    {"name": "webhook", "description": "Receives every Retell webhook event and fans it out to every enabled notifier."},
    {"name": "health", "description": "Liveness probe + list of enabled notifiers."},
]


# ─── POST /calls ──────────────────────────────────────────────────────────────

MAKE_CALL_SUMMARY = "Initiate an outbound call"
MAKE_CALL_DESCRIPTION = (
    "Forwards the request to Retell's `POST /v2/create-phone-call` and returns the "
    "registered `call_id`.\n\n"
    "- Omit `from_number` to use the `RETELL_FROM_NUMBER` configured in the environment.\n"
    "- `override_agent_id` selects which agent answers on this call only; "
    "omit it to use whichever agent is bound to `from_number` on Retell.\n"
    "- `retell_llm_dynamic_variables` injects key-value strings into the agent's prompt at runtime.\n"
    "- Retell does not support scheduled calls — every call fires immediately."
)
MAKE_CALL_RESPONSES = {
    400: {"description": "Retell rejected the request (e.g. invalid number, missing config)."},
    402: {"description": "Retell trial credit exhausted; payment required."},
    422: {"description": "Cannot find the requested asset (e.g. unknown `override_agent_id`)."},
    502: {"description": "Retell is unreachable (timeout, DNS, connection refused)."},
}
CALL_REQUEST_EXAMPLES: dict[str, dict] = {
    "minimal": {
        "summary": "Call now (minimal)",
        "description": "Place an outbound call right now. Uses `RETELL_FROM_NUMBER` from env and the agent bound to that number on Retell.",
        "value": {
            "to_number": "+91xxxxxxxxxx",
        },
    },
    "with_agent_override": {
        "summary": "With explicit agent override",
        "description": "Pin a specific agent for this call only. Useful for A/B-ing prompts without rebinding the number.",
        "value": {
            "to_number": "+91xxxxxxxxxx",
            "from_number": "+14157774444",
            "override_agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
            "override_agent_version": 1,
        },
    },
    "with_dynamic_variables": {
        "summary": "With dynamic prompt variables",
        "description": "Pass `retell_llm_dynamic_variables` keys that the agent's prompt references (e.g. `{{customer_name}}`).",
        "value": {
            "to_number": "+91xxxxxxxxxx",
            "retell_llm_dynamic_variables": {"customer_name": "Aman", "topic": "demo call"},
            "metadata": {"source": "manual-trigger"},
        },
    },
}


# ─── GET /calls/{call_id} ─────────────────────────────────────────────────────

GET_CALL_SUMMARY = "Fetch a call's full record"
GET_CALL_DESCRIPTION = (
    "Proxies Retell's `GET /v2/get-call/{call_id}`. Returns the full call record — "
    "status, transcript, telephony metadata, post-call analysis (when available), "
    "recording URL, latency stats, and cost."
)
GET_CALL_RESPONSES = {
    422: {"description": "No call exists with this id under your API key."},
    502: {"description": "Retell is unreachable."},
}


# ─── POST /alerts/{call_id} ───────────────────────────────────────────────────

ALERT_SUMMARY = "Manually fan out a notification for a call"
ALERT_DESCRIPTION = (
    "Fetches the call from Retell, then fans a `call_analyzed`-shaped notification "
    "out to every enabled notifier (Slack / Discord / Mattermost / ClickUp). "
    "Sends regardless of the call's current status. Useful for backfills or "
    "when the webhook didn't fire (e.g. local dev without a tunnel)."
)
ALERT_RESPONSES = {
    200: {
        "description": "Notification fan-out attempted. `delivered` reports per-provider outcome.",
        "content": {
            "application/json": {
                "example": {
                    "sent": True,
                    "call_id": "119c3f8e47135a29e65947eeb34cf12d",
                    "call_status": "ended",
                    "delivered": {
                        "slack": "ok",
                        "discord": "ok",
                        "mattermost": "ok",
                        "clickup": "ok",
                    },
                }
            }
        },
    },
    422: {"description": "No call exists with this id under your API key."},
    502: {"description": "Retell is unreachable."},
}


# ─── POST /webhook/retell ─────────────────────────────────────────────────────

WEBHOOK_SUMMARY = "Retell webhook receiver (fan-out)"
WEBHOOK_DESCRIPTION = (
    "Retell calls this endpoint on every subscribed event. The handler:\n\n"
    "1. Parses the `{event, call}` envelope.\n"
    "2. Fans the event out concurrently to every enabled notifier "
    "(Slack / Discord / Mattermost / ClickUp). One provider failing does not affect the others.\n"
    "3. Each provider formats the message in its native shape: Slack/Mattermost as colour-coded "
    "attachments, Discord as embeds, ClickUp as a task comment.\n\n"
    "Always returns 200 OK so Retell does not retry. The response body's `delivered` map "
    "reports per-provider outcome (`ok` or `error: …`)."
)
WEBHOOK_RESPONSES = {
    200: {
        "description": "Acknowledged. `delivered` reports per-provider outcome.",
        "content": {
            "application/json": {
                "example": {
                    "received": True,
                    "delivered": {
                        "slack": "ok",
                        "discord": "ok",
                        "mattermost": "ok",
                        "clickup": "ok",
                    },
                }
            }
        },
    }
}
WEBHOOK_OPENAPI_EXTRA = {
    "requestBody": {
        "description": (
            "Retell posts `{event, call}` for every subscribed event. The handler always "
            "returns 200 — even on parse failure — so Retell does not retry."
        ),
        "required": True,
        "content": {
            "application/json": {
                "examples": {
                    "call_started": {
                        "summary": "Call started",
                        "value": {
                            "event": "call_started",
                            "call": {
                                "call_id": "119c3f8e47135a29e65947eeb34cf12d",
                                "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
                                "call_status": "ongoing",
                                "from_number": "+14157774444",
                                "to_number": "+91xxxxxxxxxx",
                                "direction": "outbound",
                            },
                        },
                    },
                    "call_ended_user_hangup": {
                        "summary": "Call ended (user hung up)",
                        "value": {
                            "event": "call_ended",
                            "call": {
                                "call_id": "119c3f8e47135a29e65947eeb34cf12d",
                                "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
                                "call_status": "ended",
                                "duration_ms": 42000,
                                "disconnection_reason": "user_hangup",
                                "transcript": "Agent: Hi! ...\nUser: Hello.\n...",
                            },
                        },
                    },
                    "call_analyzed": {
                        "summary": "Call analyzed (full post-call data)",
                        "value": {
                            "event": "call_analyzed",
                            "call": {
                                "call_id": "119c3f8e47135a29e65947eeb34cf12d",
                                "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
                                "call_status": "ended",
                                "duration_ms": 42000,
                                "disconnection_reason": "user_hangup",
                                "transcript": "Agent: Hi! ...\nUser: Hello.\n...",
                                "call_analysis": {
                                    "call_summary": "User asked about the demo and said they would call back tomorrow.",
                                    "user_sentiment": "Positive",
                                    "call_successful": True,
                                },
                            },
                        },
                    },
                    "dial_busy": {
                        "summary": "Recipient busy (no transcript)",
                        "value": {
                            "event": "call_ended",
                            "call": {
                                "call_id": "119c3f8e47135a29e65947eeb34cf12d",
                                "agent_id": "oBeDLoLOeuAbiuaMFXRtDOLriTJ5tSxD",
                                "call_status": "ended",
                                "duration_ms": 0,
                                "disconnection_reason": "dial_busy",
                            },
                        },
                    },
                },
            }
        },
    }
}


# ─── GET /health ──────────────────────────────────────────────────────────────

HEALTH_SUMMARY = "Liveness probe + enabled-notifier inventory"
HEALTH_DESCRIPTION = (
    "Returns `{\"status\": \"ok\", \"notifiers\": [...]}` if the process is up. "
    "The `notifiers` list reports which destinations a webhook will fan out to "
    "(based on which env vars are set). No upstream calls."
)
HEALTH_RESPONSES = {
    200: {
        "content": {
            "application/json": {
                "example": {
                    "status": "ok",
                    "notifiers": ["slack", "discord", "mattermost", "clickup"],
                }
            }
        }
    }
}
