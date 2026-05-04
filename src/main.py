from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.config import settings
from src.providers.clickup import ClickUpProvider
from src.providers.discord import DiscordProvider
from src.providers.mattermost import MattermostProvider
from src.providers.retell import RetellProvider
from src.providers.slack import SlackProvider
from src.routes.alerts import router as alerts_router
from src.routes.calls import router as calls_router
from src.routes.health import router as health_router
from src.routes.webhook import router as webhook_router
from src.services.call_service import CallService
from src.utils.logger import logger
from src.utils.openapi import API_DESCRIPTION, OPENAPI_TAGS


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting calling-agent service")
    retell = RetellProvider()

    # A notifier registers itself only if its env vars are set.
    notifiers = []
    if settings.slack_bot_token and settings.slack_alert_channel:
        notifiers.append(SlackProvider())
    if settings.discord_webhook_url:
        notifiers.append(DiscordProvider())
    if settings.mattermost_webhook_url:
        notifiers.append(MattermostProvider())
    if settings.clickup_api_token and settings.clickup_task_id:
        notifiers.append(ClickUpProvider())

    app.state.retell_provider = retell
    app.state.call_service = CallService(retell)
    app.state.notifiers = notifiers

    if notifiers:
        logger.info(f"Enabled notifiers: {[n.name for n in notifiers]}")
    else:
        logger.warning(
            "No notifiers enabled — webhook events will be received but not relayed anywhere"
        )

    try:
        yield
    finally:
        logger.info("Shutting down calling-agent service")
        await retell.close()
        for n in notifiers:
            await n.close()


app = FastAPI(
    title="Calling Agent",
    description=API_DESCRIPTION,
    version="0.3.0",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(calls_router)
app.include_router(alerts_router)
app.include_router(webhook_router)


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
