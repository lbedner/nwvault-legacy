from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import flet.fastapi as flet_fastapi

from app.components.backend.hooks import backend_hooks
from app.components.backend.main import create_backend_app
from app.components.frontend.main import create_frontend_app
from app.core.config import settings
from app.core.log import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    Application lifespan manager.
    Handles startup/shutdown concerns using component-specific hooks.
    """
    # Ensure logging is configured (required for uvicorn reload mode)
    setup_logging()

    # --- STARTUP ---
    logger.info("--- Running application startup ---")

    # Discover startup and shutdown hooks
    await backend_hooks.discover_lifespan_hooks()

    # Start Flet app manager
    await flet_fastapi.app_manager.start()

    # Execute backend startup hooks
    await backend_hooks.execute_startup_hooks()

    logger.info("--- Application startup complete ---")

    yield

    # --- SHUTDOWN ---
    logger.info("--- Running application shutdown ---")

    # Execute backend shutdown hooks
    await backend_hooks.execute_shutdown_hooks()

    # Stop Flet app manager
    await flet_fastapi.app_manager.shutdown()

    logger.info("--- Application shutdown complete ---")


def create_integrated_app() -> FastAPI:
    """
    Creates the integrated Flet+FastAPI application using the officially
    recommended pattern and component-specific hooks.
    """
    app = FastAPI(lifespan=lifespan)

    create_backend_app(app)
    # Create and mount the Flet app using the flet.fastapi module
    # First, get the actual session handler function from the factory
    session_handler = create_frontend_app()
    flet_app = flet_fastapi.app(session_handler, assets_dir=settings.FLET_ASSETS_DIR)
    # Mount Flet at /dashboard to avoid intercepting FastAPI routes like /health
    app.mount("/dashboard", flet_app)

    # Mount cached vault shell assets (CSS, JS, images)
    # Uses /_assets/ to avoid conflict with /vault/{game}/... routes
    assets_dir = Path("archive/assets")
    if assets_dir.exists():
        app.mount(
            "/_assets",
            StaticFiles(directory=str(assets_dir)),
            name="vault-assets",
        )

    return app
