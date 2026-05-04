from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.providers.retell import RetellProvider
from src.providers.slack import SlackProvider
from src.routes.alerts import router as alerts_router
from src.routes.calls import router as calls_router
from src.routes.health import router as health_router
from src.routes.webhook import router as webhook_router
from src.services.alert_service import AlertService
from src.services.call_service import CallService
from src.utils.logger import logger
from src.utils.openapi import API_DESCRIPTION, OPENAPI_TAGS


# Build provider/service objects once and stash on app.state so handlers reuse them.
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting calling-agent service")
    retell_provider = RetellProvider()
    slack_provider = SlackProvider()

    app.state.retell_provider = retell_provider
    app.state.slack_provider = slack_provider
    app.state.call_service = CallService(retell_provider)  # Retell call orchestration
    app.state.alert_service = AlertService(slack_provider)  # Slack alert orchestration

    try:
        yield
    finally:
        logger.info("Shutting down calling-agent service")
        await retell_provider.close()
        await slack_provider.close()


app = FastAPI(
    title="Calling Agent",
    description=API_DESCRIPTION,
    version="0.2.0",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)
app.include_router(health_router)  # Health check
app.include_router(calls_router)  # Place / fetch Retell calls
app.include_router(alerts_router)  # Manual Slack alert by call_id
app.include_router(webhook_router)  # Retell webhook receiver


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
