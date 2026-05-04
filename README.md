# Calling Agent

A small FastAPI service that initiates outbound voice calls via **Retell AI** and posts a Slack alert for every webhook event Retell emits.

```
┌────────┐  POST /calls   ┌──────────────┐  POST /v2/    ┌───────────┐
│ Caller ├───────────────▶│ Calling      ├──────────────▶│ Retell AI │
└────────┘                │ Agent        │ create-phone- └────┬──────┘
                          │ (FastAPI)    │ call               │ webhook
                          │              │◀───────────────────┘ on every event
                          │              │   POST /webhook/retell
                          │              │
                          │              │  chat.postMessage   ┌───────┐
                          │              ├────────────────────▶│ Slack │
                          └──────────────┘                     └───────┘
```

The webhook receiver also has a sibling endpoint, `POST /alerts/{call_id}`, for **manually** triggering a Slack alert for any past call — handy when you don't want to expose your localhost via ngrok during development.

---

## Prerequisites

- **Python 3.12+** (`.python-version` pins `3.12`)
- **[uv](https://docs.astral.sh/uv/)** for dependency management (`pipx install uv` or see uv's docs)
- A Retell account with an imported phone number and at least one agent, plus a Slack workspace where you can install an app — see **[SETUP.md](SETUP.md)** for the walkthrough.

---

## Quickstart

### 1. Get your credentials

Follow **[SETUP.md](SETUP.md)** to obtain:

- `RETELL_API_KEY` — Retell dashboard
- `RETELL_FROM_NUMBER` — an E.164 number you've imported into Retell (optional default for `POST /calls`)
- `SLACK_BOT_TOKEN` — Slack app (`xoxb-…`)
- `SLACK_ALERT_CHANNEL` — channel name (no `#`) where the bot is a member
- An `agent_id` from a Retell agent you've configured (only needed when overriding the agent bound to your number)

### 2. Clone and set up the environment

```bash
git clone <this-repo>
cd retell_agent

# Install dependencies into a local .venv
uv sync

# Copy and fill in the env template
cp .env.example .env
$EDITOR .env           # paste the values from SETUP.md
```

### 3. Run the server

```bash
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The service listens on **<http://localhost:8000>**.

### 4. Open the API docs

Visit **<http://localhost:8000/docs>** — interactive Swagger UI with summaries, schemas, and ready-to-send example payloads for every endpoint.

---

## Endpoints

| Method | Path | What it does |
|---|---|---|
| `GET`  | `/health` | Liveness probe. |
| `POST` | `/calls` | Initiate an outbound call via Retell. Returns the `call_id`. |
| `GET`  | `/calls/{call_id}` | Fetch the full call record from Retell (status, transcript, telephony, analysis, recording). |
| `POST` | `/alerts/{call_id}` | Manually fetch a call and post a `call_analyzed`-shaped Slack alert (always sends). |
| `POST` | `/webhook/retell` | Retell's webhook receiver. Posts a Slack alert for every event (`call_started`, `call_ended`, `call_analyzed`, `transcript_updated`, `transfer_*`). Always returns `200`. |

### Quick test (after the server is running)

```bash
# Place a call (immediate; uses RETELL_FROM_NUMBER from .env)
curl -X POST http://localhost:8000/calls \
  -H 'Content-Type: application/json' \
  -d '{"to_number": "+91XXXXXXXXXX"}'

# Place a call with an explicit agent override
curl -X POST http://localhost:8000/calls \
  -H 'Content-Type: application/json' \
  -d '{
    "to_number": "+91XXXXXXXXXX",
    "from_number": "+14157774444",
    "override_agent_id": "<retell-agent-id>"
  }'

# Manually alert Slack for an existing call
curl -X POST http://localhost:8000/alerts/<call_id>
```

For the full set of example bodies (dynamic prompt variables, agent-version pinning, etc.), use the dropdown in the Swagger UI at `/docs`.

---

## Local development vs. live webhook

Retell's webhook posts to a public URL — your `localhost` is not reachable. So:

- **Locally** — use `POST /alerts/{call_id}`. After a call finishes on Retell, run the curl below and the Slack alert fires for that call. No tunnel, no public URL needed.

  ```bash
  curl -X POST http://localhost:8000/alerts/<call_id>
  ```

- **For real-time events** — deploy the service (see [Deployment](#deployment)) and configure your Retell agent with `webhook_url = https://<your-app>.onrender.com/webhook/retell` and the events you want (`call_started`, `call_ended`, `call_analyzed`, etc.). From then on, every subscribed event hits your live `/webhook/retell` and triggers a Slack alert automatically.

---

## Project layout

```
retell_agent/
├── README.md              # this file
├── SETUP.md               # credential walkthrough (Slack + Retell)
├── pyproject.toml         # deps + Python pin
├── uv.lock
├── .env.example
├── docs/img/              # screenshots referenced from SETUP.md
└── src/
    ├── main.py            # FastAPI app, lifespan, router registration
    ├── config.py          # pydantic-settings; loads .env
    ├── models/            # pydantic schemas (Retell request/response/webhook, Slack message)
    ├── providers/         # async httpx clients (one per upstream)
    ├── services/          # orchestration: CallService, AlertService
    ├── routes/            # FastAPI routers: calls, alerts, webhook, health
    └── utils/             # logger + OpenAPI metadata strings
```

The split is deliberate: routes call services, services call providers, providers are pure HTTP clients. No layer reaches around another.

---

## Deployment

This is a single FastAPI app — it'll run on any Python host. Below are the steps for **[Render](https://render.com)** (free tier works):

1. Push the repo to GitHub.
2. On Render: **New → Web Service**, connect the GitHub repo.
3. Configure:
   - **Runtime:** Python
   - **Build command:** `pip install uv && uv sync --frozen`
   - **Start command:** `uv run uvicorn src.main:app --host 0.0.0.0 --port $PORT`
4. Under **Environment**, add the same variables you set in `.env` (`RETELL_API_KEY`, `RETELL_BASE_URL`, `RETELL_FROM_NUMBER`, `SLACK_BOT_TOKEN`, `SLACK_BASE_URL`, `SLACK_ALERT_CHANNEL`).
5. Deploy. Render gives you a URL like `https://retell-agent.onrender.com`.
6. In the Retell dashboard, open your agent → set `webhook_url` to:

   ```
   https://<your-app>.onrender.com/webhook/retell
   ```

   and pick the events you want (`call_started`, `call_ended`, `call_analyzed`, `transcript_updated`, transfer events).

Retell will now POST to your live service for every subscribed event, and the Slack alert fires automatically.

---

## Future scope

Things deliberately left out to keep the surface area minimal for this assignment:

- **Authentication / authorization.** All endpoints are open right now — anyone who can reach the server can place calls or trigger alerts. Fine for a local / sandboxed deployment, not fine for production. The natural additions are an `X-API-Key` header check on `/calls` and `/alerts/{call_id}`, or full Bearer/JWT auth via `fastapi.security` if this ever sits behind a real client. `/webhook/retell` is a separate concern — it should verify the `x-retell-signature` header (or, simpler, an IP allowlist of `100.20.5.228`).

- **Scheduled calls.** Retell's `POST /v2/create-phone-call` has no scheduled-time field; calls fire immediately. If scheduling is needed, queue it in this service (asyncio task / APScheduler / job queue) and fire the Retell call at the scheduled instant.

- **Agent provisioning.** A `POST /agents` endpoint that creates a Retell agent with our `webhook_url` and `webhook_events` pre-wired would remove a manual dashboard step. Skipped for now per scope.

- **Batch endpoints.** Single-call/single-alert is the spec. If usage grows, the natural extensions are:
  - `POST /batch_calls` — accept a list of `CallRequestModel` and fan out via `asyncio.TaskGroup` with a `Semaphore` to cap concurrency against Retell's rate limits.
  - `POST /batch_alerts` — accept a list of `call_id`s and trigger alerts in parallel.

  None are implemented; sketches live in `temp/improvements.md`.

---

## Troubleshooting

The most common errors (token mistakes, channel membership, missing `from_number`) are documented in **[SETUP.md](SETUP.md#troubleshooting)**.
