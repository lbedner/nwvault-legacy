"""
Vault HTML fix queue — rewrites broken asset URLs in archived pages.

Disk I/O and regex processing.
"""

from arq.connections import RedisSettings

from app.components.worker.queues._base import (
    make_after_job_end,
    make_on_job_start,
    make_on_shutdown,
    make_on_startup,
)
from app.components.worker.tasks.vault_tasks import fix_html_category
from app.core.config import settings

QUEUE_NAME = "vault_fix"


class WorkerSettings:
    """Vault HTML asset fixer worker."""

    description = "Fix broken asset URLs in archived HTML"

    functions = [
        fix_html_category,
    ]

    base_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    redis_settings = RedisSettings(
        host=base_settings.host,
        port=base_settings.port,
        database=base_settings.database,
        password=base_settings.password,
        conn_timeout=settings.REDIS_CONN_TIMEOUT,
        conn_retries=settings.REDIS_CONN_RETRIES,
        conn_retry_delay=settings.REDIS_CONN_RETRY_DELAY,
    )
    queue_name = f"arq:queue:{QUEUE_NAME}"
    max_jobs = 5
    job_timeout = 300  # 5 min — fast per category
    keep_result = settings.WORKER_KEEP_RESULT_SECONDS
    max_tries = 2
    health_check_interval = settings.WORKER_HEALTH_CHECK_INTERVAL

    on_startup = make_on_startup(QUEUE_NAME)
    on_shutdown = make_on_shutdown(QUEUE_NAME)
    on_job_start = make_on_job_start(QUEUE_NAME)
    after_job_end = make_after_job_end(QUEUE_NAME)
