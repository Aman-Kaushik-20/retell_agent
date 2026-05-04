# Credentials Setup

This service supports four notification providers. Set up only the ones you want — each is independent, and missing env vars silently disable that destination. `GET /health` reports which destinations are live.

| Provider | Env vars |
|---|---|
| Slack | `SLACK_BOT_TOKEN`, `SLACK_BASE_URL`, `SLACK_ALERT_CHANNEL` |
| Discord | `DISCORD_WEBHOOK_URL` |
| Mattermost | `MATTERMOST_WEBHOOK_URL` |
| ClickUp | `CLICKUP_API_TOKEN`, `CLICKUP_TASK_ID` |
| Retell (required) | `RETELL_API_KEY`, `RETELL_BASE_URL`, `RETELL_FROM_NUMBER` (optional) |

---

## 1. Retell — get the API key

1. Sign in at <https://dashboard.retellai.com>.
2. Open **API Keys** → **Create API Key** → name it, copy the value. This is your `RETELL_API_KEY`.
3. (Optional) Import or buy a phone number under **Phone Numbers** so `POST /calls` can dial. Set the E.164 form as `RETELL_FROM_NUMBER`. If you skip this, `POST /calls` requires `from_number` in every request body. Note: Retell-purchased numbers can only dial US recipients; for international, import a Twilio/SIP number.
4. Configure your Retell agent's webhook (any subset of `call_started`, `call_ended`, `call_analyzed`, `transcript_updated`, transfer events) → `webhook_url = https://<your-deploy>/webhook/retell`.

---

## 2. Slack

The provider posts via `chat.postMessage` (not incoming webhooks) so the bot can pick its channel at request time.

1. <https://api.slack.com/apps> → **Create New App** → **From scratch**. Name it (e.g. `retell-alerts`), pick a workspace.
2. **OAuth & Permissions** → **Scopes → Bot Token Scopes** → add `chat:write`. Optionally add `chat:write.public` so the bot can post to public channels without being invited.
3. **Install to Workspace** → approve. Copy the **Bot User OAuth Token** (`xoxb-…`). That's `SLACK_BOT_TOKEN`.
4. In Slack, open the alert channel → `/invite @<your-app-name>` (skip if you have `chat:write.public`).
5. The channel name **without** `#` is `SLACK_ALERT_CHANNEL`.

Smoke test:
```bash
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d "{\"channel\": \"$SLACK_ALERT_CHANNEL\", \"text\": \"hello\"}" \
  https://slack.com/api/chat.postMessage
```

---

## 3. Discord — easiest, no app/scopes/review

1. Create a server (top-left `+` → "Create My Own"), or use one you already have.
2. Pick a channel (e.g. `#retell-alerts`) → click the gear ⚙ → **Integrations** → **Webhooks** → **New Webhook** → name it → **Copy Webhook URL**.
3. URL shape: `https://discord.com/api/webhooks/<id>/<token>`. That's `DISCORD_WEBHOOK_URL` — the only credential.

Smoke test:
```bash
curl -H 'Content-Type: application/json' \
  -d '{"content":"hello"}' \
  "$DISCORD_WEBHOOK_URL"
```

---

## 4. Mattermost — Slack-compatible payloads

Two paths — pick whichever's lighter for your environment.

### 4a. Local Docker preview (60 seconds, no signup)
```bash
docker run --rm --name mattermost-preview -d \
  --publish 8065:8065 \
  mattermost/mattermost-preview
```
- Visit <http://localhost:8065> → create the **first** account (auto-becomes admin) → create a team and channel.
- Top-left menu → **System Console** → **Integrations → Integration Management** → set **Enable Incoming Webhooks** = `true` → Save.
- Back to your team → profile menu → **Integrations** → **Incoming Webhooks** → **Add** → pick the channel → Save → copy the URL.
- URL shape: `http://localhost:8065/hooks/<hash>`.

### 4b. Mattermost Cloud trial (real public URL, good for the deployed demo)
Sign up at <https://mattermost.com/cloud-trial/>. Once you're in, the webhook setup steps from §4a from "Top-left menu →" onward are identical — just on `https://<workspace>.cloud.mattermost.com` instead of localhost.

That URL is `MATTERMOST_WEBHOOK_URL`. Slack's `{text, attachments}` JSON shape works as-is — this provider reuses the Slack formatter under the hood.

Smoke test:
```bash
curl -H 'Content-Type: application/json' \
  -d '{"text":"hello from retell-agent"}' \
  "$MATTERMOST_WEBHOOK_URL"
# expected: ok
```

> **Production caveat.** If `MATTERMOST_WEBHOOK_URL` points at `localhost`, the deployed Render service can't reach it — either skip the env var on the deploy, or use Mattermost Cloud.

---

## 5. ClickUp — task comments

Each Retell event becomes a comment on a single dedicated ClickUp task. Comments appear in the task's right-hand panel and update in real-time via websocket — visible without refresh.

### 5.1 Token
1. Sign up at <https://clickup.com> (free tier is fine).
2. Avatar (bottom-left) → **Settings** → **Apps** → **API Token** → **Generate**. Copy the value (starts with `pk_…`). That's `CLICKUP_API_TOKEN`.

### 5.2 Task ID
1. Create (or pick) a Workspace → Space → List → a single Task (e.g. "Voice Call Event Log").
2. Open the task. The URL is `https://app.clickup.com/t/<task_id>` — copy the part after `/t/`. That's `CLICKUP_TASK_ID`.

Smoke test:
```bash
curl -X POST "https://api.clickup.com/api/v2/task/$CLICKUP_TASK_ID/comment" \
  -H "Authorization: $CLICKUP_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment_text":"hello from retell-agent","notify_all":false}'
```

You should see the comment appear instantly in the task's UI.

---

## 6. Fill in `.env`

```bash
cp .env.example .env
$EDITOR .env
```

Run the server and confirm via `/health`:
```bash
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
curl -s http://localhost:8000/health
# {"status":"ok","notifiers":["slack","discord","mattermost","clickup"]}
```

---

## End-to-end smoke test (after the server is running)

```bash
curl -X POST http://localhost:8000/webhook/retell \
  -H 'Content-Type: application/json' \
  -d '{
    "event": "call_analyzed",
    "call": {
      "call_id": "smoke_001",
      "agent_id": "<retell-agent-id>",
      "call_status": "ended",
      "duration_ms": 42000,
      "disconnection_reason": "user_hangup",
      "transcript": "Agent: Hi.\nUser: Hello.",
      "call_analysis": {"call_summary": "smoke test", "user_sentiment": "Positive", "call_successful": true}
    }
  }'
```

Response:
```json
{"received": true, "delivered": {"slack": "ok", "discord": "ok", "mattermost": "ok", "clickup": "ok"}}
```

Each enabled destination gets one message in its native shape.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/health` shows `notifiers: []` | No env vars matched any provider's `is_configured()` rule | Re-check `.env` — every required var per provider must be present |
| Slack: `not_in_channel` | Bot isn't a member of `SLACK_ALERT_CHANNEL` | `/invite @<bot>` in that channel, or add `chat:write.public` and reinstall |
| Slack: `channel_not_found` | Wrong name in `.env` | Use the human-readable name without `#` |
| Discord: 401 on webhook URL | URL was rotated or deleted | Recreate the webhook on the channel |
| Mattermost: `Webhooks have been disabled` | System Console toggle off | System Console → Integrations → enable Incoming Webhooks |
| ClickUp: `Team not authorized` | Used a workspace ID where a task ID was needed | Open the task in ClickUp; the ID is the part after `/t/` in the URL |
| ClickUp: `validateListIDEx List ID invalid` | List/task ID confusion | List IDs are numeric (e.g. `901614781100`); task IDs are alphanumeric (e.g. `86d2w7fxf`). This service uses task IDs |
| Retell: `Item +XXX not found from phone-number` | `RETELL_FROM_NUMBER` isn't imported into Retell | Import the number via SIP trunking (Twilio etc.) or buy from Retell |
| Retell: `402 Payment Required` | Trial credit exhausted | Add a payment method on Retell |
| Webhook returns 200 but nothing fires | Either no notifiers are enabled, or all of them failed silently | Check `delivered` map in response body; check server logs for per-provider error |
