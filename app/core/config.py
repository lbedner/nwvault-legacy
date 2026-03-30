# app/core/config.py
"""
Application configuration management using Pydantic's BaseSettings.

This module centralizes application settings, allowing them to be loaded
from environment variables for easy configuration in different environments.
"""

from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Defines application settings.
    `model_config` is used to specify that settings should be loaded from a .env file.
    """

    # Project identity
    PROJECT_NAME: str = "nwvault-legacy"

    # Application environment: "dev" or "prod"
    APP_ENV: str = "dev"

    # Log level for the application
    LOG_LEVEL: str = "INFO"

    # Port for the web server
    PORT: int = 8000

    # Development settings
    AUTO_RELOAD: bool = False

    # Docker settings (used by docker-compose)
    AEGIS_STACK_TAG: str = "aegis-stack:latest"
    AEGIS_STACK_VERSION: str = "dev"

    # Health monitoring and alerting
    # Health checks are available via API endpoints (/health/)
    # Use external monitoring tools (Prometheus, DataDog, etc.) to poll these endpoints
    HEALTH_CHECK_ENABLED: bool = True
    HEALTH_CHECK_INTERVAL_MINUTES: int = 5  # Recommended interval for monitoring

    # Health check performance settings
    HEALTH_CHECK_TIMEOUT_SECONDS: float = 2.0
    SYSTEM_METRICS_CACHE_SECONDS: int = 5

    # Basic alerting configuration
    ALERTING_ENABLED: bool = False
    ALERT_COOLDOWN_MINUTES: int = 60  # Minutes between repeated alerts for same issue

    # Health check thresholds
    MEMORY_THRESHOLD_PERCENT: float = 90.0
    DISK_THRESHOLD_PERCENT: float = 85.0
    CPU_THRESHOLD_PERCENT: float = 95.0

    # Flet frontend settings
    FLET_ASSETS_DIR: str = "assets"  # Directory for Flet static assets (images, etc.)

    # Authentication settings
    AUTH_ENABLED: bool = True  # Set to false to disable auth (dev mode)
    SECRET_KEY: str = "change-this-secret-key-in-production-use-env-variable"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


    # Redis settings for arq background tasks
    REDIS_URL: str = "redis://redis:6379"  # Docker service name by default
    REDIS_URL_LOCAL: str | None = None  # Override for local CLI usage
    REDIS_DB: int = 0

    @property
    def redis_url_effective(self) -> str:
        """Get effective Redis URL, preferring local override when not in Docker."""
        # If explicitly overridden for local use
        if self.REDIS_URL_LOCAL and not self.is_docker:
            return self.REDIS_URL_LOCAL

        # Auto-translate Docker hostname to localhost when running outside Docker
        if not self.is_docker:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(self.REDIS_URL)
            # Only translate the default Docker service hostname "redis"
            if parsed.hostname == "redis":
                # Reconstruct URL with localhost, preserving auth, port, path, etc.
                netloc = "localhost"
                if parsed.username:
                    if parsed.password:
                        netloc = f"{parsed.username}:{parsed.password}@localhost"
                    else:
                        netloc = f"{parsed.username}@localhost"
                if parsed.port:
                    netloc = f"{netloc}:{parsed.port}"
                return urlunparse(parsed._replace(netloc=netloc))

        return self.REDIS_URL



    # arq worker settings (shared across all workers)
    WORKER_KEEP_RESULT_SECONDS: int = 3600  # Keep job results for 1 hour
    WORKER_MAX_TRIES: int = 3

    # Redis connection settings for arq workers
    REDIS_CONN_TIMEOUT: int = 5  # Connection timeout in seconds (default: 1)
    REDIS_CONN_RETRIES: int = 5  # Connection retry attempts (default: 5)
    REDIS_CONN_RETRY_DELAY: int = 1  # Delay between retries (default: 1)

    # Worker health check settings
    WORKER_HEALTH_CHECK_INTERVAL: int = 15  # In seconds (default: 15)

    # Task history retention (Redis Hashes auto-expire after this)
    TASK_HISTORY_TTL_SECONDS: int = 86400  # 24 hours

    # PURE ARQ IMPLEMENTATION - NO CONFIGURATION NEEDED!
    # Worker configuration comes from individual WorkerSettings classes
    # in app/components/worker/queues/ - just import and use as arq intended!



    # Database settings

    DATABASE_URL: str = "sqlite:///./data/app.db"
    DATABASE_ENGINE_ECHO: bool = False
    DATABASE_CONNECT_ARGS: dict[str, Any] = {"check_same_thread": False}








    # Observability (Logfire)
    # Set LOGFIRE_TOKEN to enable sending traces to Logfire cloud
    # Get a write token from https://logfire.pydantic.dev (Project Settings > Write Tokens)
    LOGFIRE_TOKEN: str | None = None

    # Read token for Logfire Query API (enables trace analytics in the Overseer dashboard)
    # Get from: Project Settings > Read Tokens in Logfire
    LOGFIRE_READ_TOKEN: str | None = None

    # Logfire project URL for linking to the dashboard
    # e.g. "https://logfire.pydantic.dev/myorg/myproject"
    LOGFIRE_PROJECT_URL: str | None = None





    # Traefik Ingress settings
    TRAEFIK_API_URL: str = "http://traefik:8080"  # Docker service name
    TRAEFIK_API_URL_LOCAL: str | None = None  # Override for local CLI usage





    @property
    def is_docker(self) -> bool:
        """Detect if running inside Docker container."""
        import os
        return (
            os.path.exists("/.dockerenv") or
            bool(os.getenv("DOCKER_CONTAINER"))
        )





    @property
    def traefik_api_url_effective(self) -> str:
        """
        Get effective Traefik API URL.

        Prefers local override when not in Docker.
        """
        # If explicitly overridden for local use
        if self.TRAEFIK_API_URL_LOCAL and not self.is_docker:
            return self.TRAEFIK_API_URL_LOCAL

        # Auto-translate Docker hostnames to localhost when running outside Docker
        if not self.is_docker:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(self.TRAEFIK_API_URL)
            # Translate Docker-specific hostnames to localhost
            if parsed.hostname == "traefik":
                netloc = "localhost"
                if parsed.port:
                    netloc = f"{netloc}:{parsed.port}"
                return urlunparse(parsed._replace(netloc=netloc))

        return self.TRAEFIK_API_URL


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def reload(self) -> None:
        """
        Reload settings from .env file in place.

        Updates all field values from a fresh Settings instance,
        allowing configuration changes to take effect without restart.
        """
        # Create a fresh Settings instance that reads from .env
        new_settings = Settings()

        # Update all field values in place
        for field_name in self.model_fields:
            setattr(self, field_name, getattr(new_settings, field_name))


settings = Settings()


def reload_settings() -> None:
    """
    Reload the global settings instance from .env file.

    Call this after modifying the .env file to pick up changes
    without restarting the application.
    """
    settings.reload()



# Pure arq queue helper functions - use dynamic discovery
def get_available_queues() -> list[str]:
    """Get all available queue names via dynamic discovery."""
    try:
        from app.components.worker.registry import discover_worker_queues
        queues: list[str] = discover_worker_queues()
        return queues
    except ImportError:
        # Worker components not available
        return []


def get_default_queue() -> str:
    """Get the default queue name for load testing."""
    # Prefer load_test queue if it exists, otherwise use first available
    available = get_available_queues()
    if "load_test" in available:
        return "load_test"
    return available[0] if available else "system"


def get_load_test_queue() -> str:
    """Get the queue name for load testing."""
    available = get_available_queues()
    return "load_test" if "load_test" in available else get_default_queue()


def is_valid_queue(queue_name: str) -> bool:
    """Check if a queue name is valid."""
    try:
        from app.components.worker.registry import validate_queue_name
        result: bool = validate_queue_name(queue_name)
        return result
    except ImportError:
        # Worker components not available, no queues are valid
        return False
