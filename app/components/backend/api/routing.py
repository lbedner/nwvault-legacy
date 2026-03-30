from fastapi import FastAPI

from app.components.backend.api import (
    admin,
    archive,
    health,
    homepage,
    task_history,
    vault,
    viewphp,
    worker,
)
from app.components.backend.api import events as worker_events


def include_routers(app: FastAPI) -> None:
    """Include all API routers in the FastAPI app"""
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(worker.router, prefix="/api/v1", tags=["worker"])
    app.include_router(task_history.router, prefix="/api/v1", tags=["task-history"])
    app.include_router(worker_events.router, prefix="/events", tags=["events"])

    # Vault routes
    app.include_router(vault.router, prefix="/api/v1/vault", tags=["vault"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    app.include_router(archive.router, prefix="/vault", tags=["archive"])

    # Homepage (site root)
    app.include_router(homepage.router, tags=["homepage"])

    # Legacy View.php controller (must be at root, no prefix)
    app.include_router(viewphp.router, tags=["viewphp"])
