# Calling Agent — multi-channel Retell event dispatcher

A small **FastAPI** service that receives webhook events from **Retell AI** and fans each event out to every configured notification destination — concurrently, with per-provider error isolation.

Currently supports four destinations:

- **Slack** — `chat.postMessage` with colour-coded attachments
- **Discord** — channel webhook with rich embeds
- **Mattermost** — incoming webhook (Slack-compatible payload)
- **ClickUp** — task comments (one comment per Retell event)

```
                                ┌──────────┐
                                │ Slack    │
                                └──────────┘
                                ▲
┌──────────┐  webhook   ┌───────┴──────┐    ┌──────────┐
│ Retell AI├───────────▶│ Calling      ├───▶│ Discord  │
└──────────┘  per-event │ Agent        │    └──────────┘
                        │ (FastAPI)    │    ┌──────────┐
                        │              ├───▶│Mattermost│
                        │              │    └──────────┘
                        │              │    ┌──────────┐
                        │              ├───▶│ ClickUp  │
                        └──────────────┘    └──────────┘
```

A provider is enabled when its env vars are present; missing vars silently disable it. `GET /health` reports which destinations are live.

A sibling endpoint `POST /alerts/{call_id}` triggers the same fan-out manually for any past Retell `call_id` — handy when developing locally without exposing your laptop via ngrok.

---

## Quickstart

```bash
git clone <this-repo>
cd retell_agent

uv sync

cp .env.example .env
$EDITOR .env       # fill in any subset of provider credentials

uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Open Swagger UI at <http://localhost:8000/docs>. Hit `/health` to confirm which notifiers your env enabled.

---

## Endpoints

| Method | Path | What it does |
|---|---|---|
| `GET`  | `/health` | Liveness probe. Body: `{status, notifiers: [...]}`. |
| `POST` | `/calls` | Initiate an outbound call via Retell. Returns the registered `call_id`. |
| `GET`  | `/calls/{call_id}` | Fetch the full call record from Retell (status / transcript / analysis / recording / cost). |
| `POST` | `/alerts/{call_id}` | Manually fan a `call_analyzed`-shaped notification out to every enabled provider. |
| `POST` | `/webhook/retell` | Retell's webhook receiver. Fans every event out to every enabled provider. Always returns 200. |

The webhook + manual-alert responses both include a `delivered` map reporting per-provider outcome:

```json
{"received": true, "delivered": {"slack": "ok", "discord": "ok", "mattermost": "ok", "clickup": "ok"}}
```

---

## Provider setup

Each provider is independent — set up only the ones you want. See **[SETUP.md](SETUP.md)** for screenshot-level walkthroughs of all four.

| Provider | Env vars | Credentials |
|---|---|---|
| Slack | `SLACK_BOT_TOKEN`, `SLACK_BASE_URL`, `SLACK_ALERT_CHANNEL` | Bot User OAuth Token (`xoxb-…`) with `chat:write`. Bot must be in the target channel. |
| Discord | `DISCORD_WEBHOOK_URL` | Channel → Edit Channel → Integrations → Webhooks → New. The URL is the only credential. |
| Mattermost | `MATTERMOST_WEBHOOK_URL` | Incoming webhook URL — local Docker preview, Mattermost Cloud trial, or self-hosted. Slack-compatible JSON shape. |
| ClickUp | `CLICKUP_API_TOKEN`, `CLICKUP_TASK_ID` | Personal API token (`pk_…`) + the ID of the task that should receive comments. |

Retell credentials remain required to fetch call data:

| Var | Required | Default |
|---|---|---|
| `RETELL_API_KEY` | yes | — |
| `RETELL_BASE_URL` | no | `https://api.retellai.com` |
| `RETELL_FROM_NUMBER` | no | optional default for `POST /calls` |

---

## How fan-out works

```python
# src/services/notifier_service.py
async def fanout(self, event, call) -> dict[str, str]:
    results = await asyncio.gather(
        *(n.send(event, call) for n in self.notifiers),
        return_exceptions=True,
    )
    return {n.name: ("ok" if not isinstance(r, Exception) else f"error: {r!r}")
            for n, r in zip(self.notifiers, results)}
```

- **All providers fire concurrently** via `asyncio.gather`.
- `return_exceptions=True` isolates per-provider failures — Slack 401-ing won't stop Discord from posting.
- Every error is logged with the provider name and event/call IDs.
- The webhook handler always returns 200 to Retell regardless of any provider failure (Retell otherwise retries up to 3×).

Each provider implements the same minimal surface:

```python
class XProvider:
    name: str
    async def send(event: WebhookEventType, call: CallObject) -> None: ...
    async def close() -> None: ...
```

---

## Local development vs. deployed webhook

Retell only POSTs to public URLs — `localhost` is unreachable. So:

- **Local**: use `POST /alerts/{call_id}`. After a call completes on Retell, run the curl below and the fan-out fires for that call. No tunnel needed.

  ```bash
  curl -X POST http://localhost:8000/alerts/<call_id>
  ```

- **Deployed**: configure the Retell agent's `webhook_url = https://<your-app>/webhook/retell` and the events you want (`call_started`, `call_ended`, `call_analyzed`, `transcript_updated`, transfer events). Every subscribed event hits your service and fans out automatically.

A live deployment exists at `https://retell-agent-6ark.onrender.com` (Render free tier).

> **Mattermost note:** if you point at a local Docker preview (`http://localhost:8065/...`), the deployed instance can't reach it. Either skip `MATTERMOST_WEBHOOK_URL` on the deploy, or use Mattermost Cloud / a public self-host.

---

## Project layout

```
retell_agent/
├── README.md              # this file
├── SETUP.md               # credential walkthroughs (Slack + Discord + Mattermost + ClickUp + Retell)
├── pyproject.toml         # deps + Python pin
├── .env.example
├── docs/img/
└── src/
    ├── main.py            # FastAPI app, lifespan, conditional notifier construction
    ├── config.py          # pydantic-settings; loads .env
    ├── models/
    │   ├── retell.py      # CallStatus, WebhookEventType, DisconnectionReason, CallObject, ...
    │   └── slack.py       # Slack-compatible attachment/message shapes (also used by Mattermost)
    ├── providers/
    │   ├── retell.py      # Retell HTTP client (calls + executions)
    │   ├── slack.py       # Slack notifier
    │   ├── discord.py     # Discord notifier
    │   ├── mattermost.py  # Mattermost notifier (reuses Slack formatter)
    │   ├── clickup.py     # ClickUp notifier (task comments)
    │   └── _attachment.py # shared Slack/Mattermost attachment builder
    ├── services/
    │   ├── call_service.py
    │   └── notifier_service.py  # fan-out via asyncio.gather
    ├── routes/            # calls, alerts, webhook, health
    └── utils/             # logger + OpenAPI metadata
```

The split is deliberate: routes call services, services call providers, providers are pure HTTP clients. Each provider owns both its HTTP and its formatter.

---

## Deployment

This is a single FastAPI app — runs anywhere Python does. Steps for **[Render](https://render.com)** (free tier):

1. Push to GitHub.
2. Render → **New → Web Service**, connect the repo.
3. Configure:
   - **Runtime**: Python
   - **Build command**: `pip install uv && uv sync --frozen`
   - **Start command**: `uv run uvicorn src.main:app --host 0.0.0.0 --port $PORT`
4. Environment: paste in whichever provider env vars you want enabled in production. Skip the rest — they auto-disable.
5. Deploy. Take the resulting URL and set `webhook_url = https://<your-app>/webhook/retell` on your Retell agent.

---

## Future scope

Deliberately not built — confirm before adding:

- **Authentication** on `/calls` and `/alerts/{call_id}`. Currently open.
- **Webhook signature verification** for Retell's `x-retell-signature` header.
- **Per-request routing** (`notify_to: ["slack","discord"]` knob on `/alerts/{call_id}`) to fan out to a subset.
- **Retries / dead-letter** when a provider fails. Currently we log and move on.
- **Scheduled calls.** Retell has no scheduling API.
- **Agent provisioning.** Retell agents created via dashboard.
- **Batch endpoints** (`/batch_calls`, `/batch_alerts`).

Sketches in [temp/improvements.md](temp/improvements.md).
