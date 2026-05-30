from fastapi import FastAPI

from backend.api.routers.auth import router as auth_router
from backend.api.routers.personalization import router as personalization_router
from backend.api.routers.user_planning import router as user_planning_router
from backend.api.routers.scheduler import router as scheduler_router
from backend.api.routers.scorer import router as scorer_router


def register_routers(app: FastAPI) -> None:
    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(scheduler_router, prefix="/api/schedules", tags=["Scheduler"])
    app.include_router(
        personalization_router,
        prefix="/api/users",
        tags=["User Personalization"],
    )
    app.include_router(
        user_planning_router,
        prefix="/api/users",
        tags=["User Planning"],
    )
    app.include_router(
        scorer_router,
        prefix="/api/scorer",
        tags=["Scorer"],
    )
