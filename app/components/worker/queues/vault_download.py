"""
Vault download queue — fetches files from rolovault archive.

Network I/O bound, long-running tasks.
"""

from arq.connections import RedisSettings

from app.components.worker.queues._base import (
    make_after_job_end,
    make_on_job_start,
    make_on_shutdown,
    make_on_startup,
)
from app.components.worker.tasks.vault_tasks import (
    download_category,
    download_xml_data,
    enqueue_review_scrape,
    scrape_review,
)
from app.core.config import settings

QUEUE_NAME = "vault_download"


class WorkerSettings:
    """Vault archive download worker."""

    description = "Archive file downloads from rolovault"

    functions = [
        download_xml_data,
        download_category,
        enqueue_review_scrape,
        scrape_review,
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
    max_jobs = 1  # Serial for Wayback rate limiting
    job_timeout = 3600  # 1 hour
    keep_result = settings.WORKER_KEEP_RESULT_SECONDS
    max_tries = 3  # Retry failed Wayback requests
    health_check_interval = settings.WORKER_HEALTH_CHECK_INTERVAL

    on_startup = make_on_startup(QUEUE_NAME)
    on_shutdown = make_on_shutdown(QUEUE_NAME)
    on_job_start = make_on_job_start(QUEUE_NAME)
    after_job_end = make_after_job_end(QUEUE_NAME)
