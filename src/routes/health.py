from fastapi import APIRouter, Request

from src.utils.openapi import HEALTH_DESCRIPTION, HEALTH_RESPONSES, HEALTH_SUMMARY

router = APIRouter()


# Liveness probe + the names of the notifiers wired up in lifespan.
@router.get(
    "/health",
    tags=["health"],
    summary=HEALTH_SUMMARY,
    description=HEALTH_DESCRIPTION,
    responses=HEALTH_RESPONSES,
)
async def health(request: Request) -> dict[str, object]:
    notifiers = getattr(request.app.state, "notifiers", [])
    return {
        "status": "ok",
        "notifiers": [n.name for n in notifiers],
    }
