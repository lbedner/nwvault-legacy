from fastapi import FastAPI

from app.components.backend.api import health
from app.components.backend.api import events as worker_events
from app.components.backend.api import task_history
from app.components.backend.api import worker


def include_routers(app: FastAPI) -> None:
    """Include all API routers in the FastAPI app"""
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(worker.router, prefix="/api/v1", tags=["worker"])
    app.include_router(task_history.router, prefix="/api/v1", tags=["task-history"])
    app.include_router(worker_events.router, prefix="/events", tags=["events"])
