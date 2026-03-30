"""Shared lifecycle hooks for worker queues."""

from typing import Any

from arq.constants import result_key_prefix
from arq.jobs import deserialize_result
import redis.asyncio as aioredis

from app.components.worker.events import publish_event
from app.core.config import settings
from app.core.log import logger


def make_on_startup(queue_name: str):
    """Create an on_startup hook for a named queue."""

    async def on_startup(ctx: dict[str, Any]) -> None:
        try:
            redis_url = (
                settings.redis_url_effective
                if hasattr(settings, "redis_url_effective")
                else settings.REDIS_URL
            )
            ctx["events_redis"] = aioredis.from_url(redis_url)
            ctx["worker_queue_name"] = queue_name
            await publish_event(
                ctx["events_redis"], "worker.started", queue_name,
            )
        except Exception as e:
            logger.debug(f"Failed to init event publishing: {e}")

    return staticmethod(on_startup)


def make_on_shutdown(queue_name: str):
    """Create an on_shutdown hook for a named queue."""

    async def on_shutdown(ctx: dict[str, Any]) -> None:
        if "events_redis" in ctx:
            await publish_event(
                ctx["events_redis"], "worker.stopped", queue_name,
            )
            await ctx["events_redis"].aclose()

    return staticmethod(on_shutdown)


def make_on_job_start(queue_name: str):
    """Create an on_job_start hook for a named queue."""

    async def on_job_start(ctx: dict[str, Any]) -> None:
        if "events_redis" in ctx:
            job_id = str(ctx.get("job_id", "unknown"))
            await publish_event(
                ctx["events_redis"],
                "job.started",
                queue_name,
                {"job_id": job_id},
            )
            from app.components.worker.task_history import (
                record_task_started,
                resolve_arq_task_name,
            )

            task_name = await resolve_arq_task_name(
                ctx["events_redis"], job_id,
            )
            await record_task_started(
                ctx["events_redis"],
                job_id,
                task_name=task_name,
                queue_name=queue_name,
            )

    return staticmethod(on_job_start)


def make_after_job_end(queue_name: str):
    """Create an after_job_end hook for a named queue."""

    async def after_job_end(ctx: dict[str, Any]) -> None:
        if "events_redis" not in ctx:
            return

        job_id = str(ctx.get("job_id", "unknown"))

        success = True
        error_msg: str | None = None
        task_name: str | None = None
        try:
            raw = await ctx["events_redis"].get(
                result_key_prefix + job_id,
            )
            if raw:
                result = deserialize_result(raw)
                success = result.success
                task_name = result.function
                if not success and result.result:
                    error_msg = str(result.result)
        except Exception:
            pass

        event_type = "job.completed" if success else "job.failed"
        await publish_event(
            ctx["events_redis"],
            event_type,
            queue_name,
            {
                "job_id": job_id,
                "status": "success" if success else "failed",
            },
        )

        from app.components.worker.task_history import (
            record_task_finished,
        )

        await record_task_finished(
            ctx["events_redis"],
            job_id,
            success=success,
            error=error_msg,
            task_name=task_name,
            queue_name=queue_name,
        )

    return staticmethod(after_job_end)
