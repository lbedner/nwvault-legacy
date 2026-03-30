"""
Auto-discovered Logfire observability middleware.

Configures Logfire and instruments FastAPI and other enabled components.
When LOGFIRE_TOKEN is not set, instrumentation still runs but no data
is sent to Logfire cloud. Set LOGFIRE_TOKEN in .env to enable.
"""

from fastapi import FastAPI
import logfire

from app.core.config import settings
from app.core.log import logger


def register_middleware(app: FastAPI) -> None:
    """Configure Logfire observability and instrument the application."""
    logfire.configure(
        service_name=settings.PROJECT_NAME,
        environment=settings.APP_ENV,
        send_to_logfire=bool(settings.LOGFIRE_TOKEN),
        console=False,
    )

    # Instrument FastAPI (always)
    logfire.instrument_fastapi(app, excluded_urls="/health/.*|/dashboard/.*")
    logger.info("Logfire: FastAPI instrumented")

    # Instrument HTTPX (always -- httpx is a core dependency)
    logfire.instrument_httpx()
    logger.info("Logfire: HTTPX instrumented")

    # Instrument SQLAlchemy/SQLModel (database component enabled)
    try:
        from app.core.db import engine

        logfire.instrument_sqlalchemy(engine=engine)
        logger.info("Logfire: SQLAlchemy instrumented")
    except Exception as e:
        logger.warning(f"Logfire: Could not instrument SQLAlchemy: {e}")

    # Instrument Redis (redis component enabled)
    try:
        logfire.instrument_redis()
        logger.info("Logfire: Redis instrumented")
    except Exception as e:
        logger.warning(f"Logfire: Could not instrument Redis: {e}")

    if settings.LOGFIRE_TOKEN:
        logger.info("Logfire observability active (sending to Logfire cloud)")
    else:
        logger.info("Logfire instrumentation active (no token -- cloud disabled)")
