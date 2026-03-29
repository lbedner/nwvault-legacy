"""
Load testing CLI commands.

Provides command-line interface for running and managing load tests,
with full parameter configuration and result analysis.
"""

import asyncio
from enum import Enum
import json
import time
from typing import Any

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
import typer

from app.components.worker.constants import LoadTestTypes
from app.core.config import get_load_test_queue
from app.core.log import logger
from app.i18n import lazy_t, t
from app.services.load_test import (
    LoadTestConfiguration,
    LoadTestService,
    quick_cpu_test,
    quick_io_test,
    quick_memory_test,
)

app = typer.Typer(
    name="load-test",
    help=lazy_t("loadtest.help"),
    no_args_is_help=True,
)

console = Console()


class QueueChoice(str, Enum):
    """Available queue types for load testing."""

    load_test = "load_test"
    system = "system"  # Legacy option
    media = "media"  # Legacy option

    @classmethod
    def get_default(cls) -> str:
        """Get the default queue from config."""
        return get_load_test_queue()


def _get_test_type_info_i18n(test_type: LoadTestTypes) -> dict[str, Any]:
    """Get test type info with translated strings overlaid on service data."""
    info = LoadTestService.get_test_type_info(test_type)
    key = test_type.value
    info["name"] = t(f"loadtest.type.{key}.name")
    info["description"] = t(f"loadtest.type.{key}.description")
    info["performance_signature"] = t(f"loadtest.type.{key}.signature")
    info["typical_duration_ms"] = t(f"loadtest.type.{key}.duration")
    info["concurrency_impact"] = t(f"loadtest.type.{key}.concurrency")
    return info


def _t_status(status: str) -> str:
    """Translate a status value at display time."""
    key = f"loadtest.status.{status}"
    translated = t(key)
    return translated if translated != key else status


def _t_rating(rating: str) -> str:
    """Translate a rating value at display time."""
    key = f"loadtest.rating.{rating}"
    translated = t(key)
    return translated if translated != key else rating


def _t_pressure(pressure: str) -> str:
    """Translate a queue pressure value at display time."""
    key = f"loadtest.pressure.{pressure}"
    translated = t(key)
    return translated if translated != key else pressure


def _t_validation(value: object) -> str:
    """Translate a validation value at display time."""
    if isinstance(value, bool):
        return t("loadtest.validation.yes") if value else t("loadtest.validation.no")
    key = f"loadtest.validation.{value}"
    translated = t(key)
    return translated if translated != key else str(value)


def _t_recommendations(recs: list[str]) -> list[str]:
    """Translate known recommendation strings at display time."""
    result = []
    for rec in recs:
        if "Low throughput" in rec:
            result.append(t("loadtest.rec.low_throughput"))
        elif "High failure rate" in rec:
            # Extract the rate value
            import re
            match = re.search(r"([\d.]+)%", rec)
            rate = match.group(1) if match else "?"
            result.append(t("loadtest.rec.high_failure", rate=rate))
        elif "Long execution time" in rec:
            result.append(t("loadtest.rec.long_execution"))
        else:
            result.append(rec)
    return result


@app.command("run", help=lazy_t("loadtest.help_run"))
def run_load_test(
    num_tasks: int = typer.Option(
        100, "--tasks", "-n", help=lazy_t("loadtest.opt_num_tasks"), min=1
    ),
    task_type: LoadTestTypes = typer.Option(
        LoadTestTypes.CPU_INTENSIVE, "--type", "-t", help=lazy_t("loadtest.opt_task_type")
    ),
    batch_size: int = typer.Option(
        10, "--batch", "-b", help=lazy_t("loadtest.opt_batch_size"), min=1, max=100
    ),
    delay_ms: int = typer.Option(
        0, "--delay", "-d", help=lazy_t("loadtest.opt_delay"), min=0, max=5000
    ),
    target_queue: QueueChoice = typer.Option(
        QueueChoice.load_test, "--queue", "-q", help=lazy_t("loadtest.opt_queue")
    ),
    wait: bool = typer.Option(
        True, "--wait/--no-wait", help=lazy_t("loadtest.opt_wait")
    ),
    timeout: int = typer.Option(
        600, "--timeout", help=lazy_t("loadtest.opt_timeout"), min=10, max=3600
    ),
) -> None:
    config = LoadTestConfiguration(
        num_tasks=num_tasks,
        task_type=task_type,
        batch_size=batch_size,
        delay_ms=delay_ms,
        target_queue=target_queue.value,
    )

    # Display test configuration
    _display_test_configuration(config, task_type.value)

    # Enqueue the load test
    rprint(f"[bold blue]{t('loadtest.starting')}[/bold blue]")

    try:
        # Use single asyncio.run() for both enqueue and wait to avoid
        # 'Event loop is closed' errors from Redis connection cleanup
        task_id, result = asyncio.run(
            _run_load_test_and_wait(config, target_queue.value, timeout, wait)
        )

        rprint(f"[green]{t('loadtest.enqueued')}[/green]")
        rprint(f"[cyan]{t('loadtest.task_id_label')}[/cyan] {task_id}")

        if wait:
            if result is None:
                rprint(f"\n[red]{t('loadtest.timeout_reached', timeout=timeout)}[/red]")
                rprint(
                    f"[yellow]{t('loadtest.check_results_manual')}[/yellow] "
                    f"nwvault-legacy load-test results {task_id}"
                )
            else:
                rprint(f"\n [bold green]{t('loadtest.completed')}[/bold green]")
                _display_load_test_results(result, detailed=True)
        else:
            rprint(f"\n[yellow]{t('loadtest.check_results_later')}[/yellow]")
            rprint(
                f"   [bold]nwvault-legacy load-test results "
                f"{task_id}[/bold]"
            )

    except Exception as e:
        rprint(f"[red]{t('loadtest.start_failed')}[/red] {e}")
        raise typer.Exit(1)


@app.command("cpu", help=lazy_t("loadtest.help_cpu"))
def quick_cpu_test_cmd(
    num_tasks: int = typer.Option(
        50, "--tasks", "-n", help=lazy_t("loadtest.opt_cpu_tasks"), min=1
    ),
    wait: bool = typer.Option(True, "--wait/--no-wait", help=lazy_t("loadtest.opt_wait_short")),
) -> None:
    rprint(f"[bold blue]{t('loadtest.quick_cpu_title')}[/bold blue]")
    rprint(f"[cyan]{t('loadtest.tasks_label')}[/cyan] {t('loadtest.quick_cpu_tasks', count=num_tasks)}")
    rprint(f"[cyan]{t('loadtest.work_type_label')}[/cyan] {t('loadtest.quick_cpu_work')}")

    try:
        # Use single asyncio.run() for both enqueue and wait to avoid
        # 'Event loop is closed' errors from Redis connection cleanup
        task_id, result = asyncio.run(
            _run_quick_test_and_wait(quick_cpu_test, num_tasks, wait)
        )
        rprint(f"[green]{t('loadtest.cpu_started')}[/green] {t('loadtest.task_id_label')} {task_id}")

        if wait:
            if result is None:
                rprint(f"\n[red]{t('loadtest.timeout_progress')}[/red]")
                rprint(
                    f"[yellow]{t('loadtest.check_results')}[/yellow] "
                    f"nwvault-legacy load-test results {task_id}"
                )
            else:
                rprint(f"\n [bold green]{t('loadtest.completed')}[/bold green]")
                _display_load_test_results(result, detailed=True)
        else:
            rprint(
                f"[yellow]{t('loadtest.check_results')}[/yellow] "
                f"nwvault-legacy load-test results {task_id}"
            )

    except Exception as e:
        rprint(f"[red]{t('loadtest.cpu_failed')}[/red] {e}")
        raise typer.Exit(1)


@app.command("io", help=lazy_t("loadtest.help_io"))
def quick_io_test_cmd(
    num_tasks: int = typer.Option(
        100, "--tasks", "-n", help=lazy_t("loadtest.opt_io_tasks"), min=1
    ),
    wait: bool = typer.Option(True, "--wait/--no-wait", help=lazy_t("loadtest.opt_wait_short")),
) -> None:
    rprint(f"[bold blue]{t('loadtest.quick_io_title')}[/bold blue]")
    rprint(f"[cyan]{t('loadtest.tasks_label')}[/cyan] {t('loadtest.quick_io_tasks', count=num_tasks)}")
    rprint(f"[cyan]{t('loadtest.work_type_label')}[/cyan] {t('loadtest.quick_io_work')}")

    try:
        # Use single asyncio.run() for both enqueue and wait to avoid
        # 'Event loop is closed' errors from Redis connection cleanup
        task_id, result = asyncio.run(
            _run_quick_test_and_wait(quick_io_test, num_tasks, wait)
        )
        rprint(f"[green]{t('loadtest.io_started')}[/green] {t('loadtest.task_id_label')} {task_id}")

        if wait:
            if result is None:
                rprint(f"\n[red]{t('loadtest.timeout_progress')}[/red]")
                rprint(
                    f"[yellow]{t('loadtest.check_results')}[/yellow] "
                    f"nwvault-legacy load-test results {task_id}"
                )
            else:
                rprint(f"\n [bold green]{t('loadtest.completed')}[/bold green]")
                _display_load_test_results(result, detailed=True)
        else:
            rprint(
                f"[yellow]{t('loadtest.check_results')}[/yellow] "
                f"nwvault-legacy load-test results {task_id}"
            )

    except Exception as e:
        rprint(f"[red]{t('loadtest.io_failed')}[/red] {e}")
        raise typer.Exit(1)


@app.command("memory", help=lazy_t("loadtest.help_memory"))
def quick_memory_test_cmd(
    num_tasks: int = typer.Option(
        200, "--tasks", "-n", help=lazy_t("loadtest.opt_memory_tasks"), min=1
    ),
    wait: bool = typer.Option(True, "--wait/--no-wait", help=lazy_t("loadtest.opt_wait_short")),
) -> None:
    rprint(f"[bold blue]{t('loadtest.quick_memory_title')}[/bold blue]")
    rprint(f"[cyan]{t('loadtest.tasks_label')}[/cyan] {t('loadtest.quick_memory_tasks', count=num_tasks)}")
    rprint(f"[cyan]{t('loadtest.work_type_label')}[/cyan] {t('loadtest.quick_memory_work')}")

    try:
        # Use single asyncio.run() for both enqueue and wait to avoid
        # 'Event loop is closed' errors from Redis connection cleanup
        task_id, result = asyncio.run(
            _run_quick_test_and_wait(quick_memory_test, num_tasks, wait)
        )
        rprint(f"[green]{t('loadtest.memory_started')}[/green] {t('loadtest.task_id_label')} {task_id}")

        if wait:
            if result is None:
                rprint(f"\n[red]{t('loadtest.timeout_progress')}[/red]")
                rprint(
                    f"[yellow]{t('loadtest.check_results')}[/yellow] "
                    f"nwvault-legacy load-test results {task_id}"
                )
            else:
                rprint(f"\n [bold green]{t('loadtest.completed')}[/bold green]")
                _display_load_test_results(result, detailed=True)
        else:
            rprint(
                f"[yellow]{t('loadtest.check_results')}[/yellow] "
                f"nwvault-legacy load-test results {task_id}"
            )

    except Exception as e:
        rprint(f"[red]{t('loadtest.memory_failed')}[/red] {e}")
        raise typer.Exit(1)


@app.command("results", help=lazy_t("loadtest.help_results"))
def show_results(
    task_id: str = typer.Argument(..., help=lazy_t("loadtest.arg_task_id")),
    target_queue: QueueChoice = typer.Option(
        QueueChoice.load_test, "--queue", "-q", help=lazy_t("loadtest.opt_queue_results")
    ),
    detailed: bool = typer.Option(
        False, "--detailed", "-d", help=lazy_t("loadtest.opt_detailed")
    ),
    json_output: bool = typer.Option(
        False, "--json", help=lazy_t("loadtest.opt_json")
    ),
) -> None:
    try:
        result = asyncio.run(
            LoadTestService.get_load_test_result(task_id, target_queue.value)
        )

        if not result:
            rprint(f"[red]{t('loadtest.no_results')}[/red] {task_id}")
            rprint(f"[yellow]{t('loadtest.check_task_hint')}[/yellow]")
            raise typer.Exit(1)

        if json_output:
            print(json.dumps(result, indent=2, default=str))
            return

        _display_load_test_results(result, detailed)

    except Exception as e:
        rprint(f"[red]{t('loadtest.results_failed')}[/red] {e}")
        raise typer.Exit(1)


@app.command("info", help=lazy_t("loadtest.help_info"))
def show_test_type_info(
    test_type: str | None = typer.Argument(
        None, help=lazy_t("loadtest.arg_test_type")
    ),
) -> None:
    if test_type:
        # Show detailed info for specific test type
        try:
            test_type_enum = LoadTestTypes(test_type)
            info = _get_test_type_info_i18n(test_type_enum)
            _display_test_type_info(test_type, info)
        except ValueError:
            rprint(f"[red]{t('loadtest.unknown_type')}[/red] {test_type}")
            rprint(
                f"[yellow]{t('loadtest.available_types_list')}[/yellow] cpu_intensive, io_simulation, "
                "memory_operations, failure_testing"
            )
            raise typer.Exit(1)
    else:
        # Show overview of all test types
        rprint(f"[bold blue]{t('loadtest.available_types')}[/bold blue]\n")

        for load_test_type in [
            LoadTestTypes.CPU_INTENSIVE,
            LoadTestTypes.IO_SIMULATION,
            LoadTestTypes.MEMORY_OPERATIONS,
            LoadTestTypes.FAILURE_TESTING,
        ]:
            info = _get_test_type_info_i18n(load_test_type)
            rprint(
                f"  [bold cyan]{load_test_type}[/bold cyan] - "
                f"{info.get('name', '')}"
            )
            rprint(f"   {info.get('description', '')}")
            rprint(
                f"   [dim]{t('loadtest.typical_duration')} "
                f"{info.get('typical_duration_ms', '')}[/dim]\n"
            )

        rprint(f"[yellow]{t('loadtest.use_help_hint')}[/yellow]")
        rprint(f"[cyan]{t('loadtest.examples_label')}[/cyan]")
        rprint("   nwvault-legacy load-test info cpu_intensive")
        rprint("   nwvault-legacy load-test info io_simulation")
        rprint("   nwvault-legacy load-test info memory_operations")


def _display_test_configuration(config: LoadTestConfiguration, test_type: str) -> None:
    """Display load test configuration in a formatted panel."""

    test_info = _get_test_type_info_i18n(LoadTestTypes(test_type))

    config_text = (
        f"[bold cyan]{t('loadtest.config_title')}[/bold cyan]\n\n"
        f"[cyan]{t('loadtest.config_tasks')}[/cyan] {t('loadtest.config_tasks_detail', count=config.num_tasks, type=test_type)}\n"
        f"[cyan]{t('loadtest.config_batching')}[/cyan] {t('loadtest.config_batch_detail', size=config.batch_size)}\n"
        f"[cyan]{t('loadtest.config_delay')}[/cyan] {t('loadtest.config_delay_detail', ms=config.delay_ms)}\n"
        f"[cyan]{t('loadtest.config_queue')}[/cyan] {config.target_queue}\n\n"
        f"[bold yellow]{t('loadtest.type_details_title')}[/bold yellow]\n"
        f"[yellow]{t('loadtest.type_name')}[/yellow] {test_info.get('name', '')}\n"
        f"[yellow]{t('loadtest.type_description')}[/yellow] {test_info.get('description', '')}\n"
        f"[yellow]{t('loadtest.type_performance')}[/yellow] {test_info.get('performance_signature', '')}\n"
        f"[yellow]{t('loadtest.type_concurrency')}[/yellow] {test_info.get('concurrency_impact', '')}"
    )

    console.print(Panel(config_text, title=t("loadtest.panel_setup"), border_style="blue"))


def _display_test_type_info(test_type: str, info: dict[str, Any]) -> None:
    """Display detailed information about a specific test type."""

    info_text = (
        f"[bold cyan]{info.get('name', '')}[/bold cyan]\n\n"
        f"[bold yellow]{t('loadtest.type_description')}[/bold yellow]\n"
        f"{info.get('description', '')}\n\n"
        f"[bold yellow]{t('loadtest.type_performance')}[/bold yellow]\n"
        f"{info.get('performance_signature', '')}\n"
        f"[yellow]{t('loadtest.typical_duration')}[/yellow] {info.get('typical_duration_ms', '')}\n"
        f"[yellow]{t('loadtest.type_concurrency')}[/yellow] {info.get('concurrency_impact', '')}"
    )

    console.print(
        Panel(info_text, title=f"{test_type}", border_style="green")
    )


async def _poll_for_result_with_progress(
    task_id: str, target_queue: str, timeout: int
) -> dict[str, Any] | None:
    """
    Poll for load test result with progress display.

    Uses a single event loop for all async operations to avoid
    'Event loop is closed' errors from orphaned Redis connections.
    """
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        wait_task = progress.add_task(
            t("loadtest.waiting_progress"), total=None
        )

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout:
                progress.update(wait_task, description=t("loadtest.timeout_progress"))
                return None

            try:
                result = await LoadTestService.get_load_test_result(
                    task_id, target_queue
                )
                if result:
                    return result
            except Exception as e:
                logger.debug(f"Error checking results: {e}")

            progress.update(
                wait_task, description=t("loadtest.waiting_elapsed", elapsed=f"{elapsed:.1f}")
            )
            await asyncio.sleep(2)


async def _run_load_test_and_wait(
    config: LoadTestConfiguration,
    target_queue: str,
    timeout: int,
    wait: bool,
) -> tuple[str, dict[str, Any] | None]:
    """
    Run load test enqueue and optional wait in single event loop.

    Combines enqueue and polling to avoid 'Event loop is closed' errors
    from Redis connections that span multiple asyncio.run() calls.
    """

    from app.components.worker.pools import clear_pool_cache


    try:
        task_id = await LoadTestService.enqueue_load_test(config)

        if not wait:
            return task_id, None

        rprint(
            f"\n[yellow]{t('loadtest.waiting', timeout=timeout)}"
            f"[/yellow]"
        )
        result = await _poll_for_result_with_progress(task_id, target_queue, timeout)
        return task_id, result
    finally:

        await clear_pool_cache()



async def _run_quick_test_and_wait(
    quick_test_func: Any,
    num_tasks: int,
    wait: bool,
    timeout: int = 600,
) -> tuple[str, dict[str, Any] | None]:
    """
    Run quick test enqueue and optional wait in single event loop.

    Combines enqueue and polling to avoid 'Event loop is closed' errors.
    """

    from app.components.worker.pools import clear_pool_cache


    try:
        task_id = await quick_test_func(num_tasks)

        if not wait:
            return task_id, None

        rprint(
            f"\n[yellow]{t('loadtest.waiting', timeout=timeout)}"
            f"[/yellow]"
        )
        result = await _poll_for_result_with_progress(
            task_id, get_load_test_queue(), timeout
        )
        return task_id, result
    finally:

        await clear_pool_cache()



def _display_load_test_results(result: dict[str, Any], detailed: bool = False) -> None:
    """Display formatted load test results."""

    # Basic results
    status = result.get("status", "unknown")

    # Handle timeout and failure cases
    if status in ["timed_out", "failed"]:
        _display_error_result(result, status)
        return

    # Handle successful results
    metrics = result.get("metrics", {})

    # Create summary table for successful results
    table = Table(
        title=t("loadtest.results_title"),
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column(t("loadtest.metric_column"), style="cyan", no_wrap=True)
    table.add_column(t("loadtest.value_column"), style="green")
    table.add_column(t("loadtest.details_column"), style="dim")

    # Add basic metrics
    table.add_row(t("loadtest.metric_status"), _t_status(status), t("loadtest.detail_status"))
    table.add_row(
        t("loadtest.metric_tasks_sent"), str(metrics.get("tasks_sent", "unknown")), t("loadtest.detail_tasks_sent")
    )
    table.add_row(
        t("loadtest.metric_tasks_completed"),
        str(metrics.get("tasks_completed", "unknown")),
        t("loadtest.detail_tasks_completed"),
    )
    table.add_row(
        t("loadtest.metric_tasks_failed"),
        str(metrics.get("tasks_failed", "unknown")),
        t("loadtest.detail_tasks_failed"),
    )
    table.add_row(
        t("loadtest.metric_duration"),
        f"{metrics.get('total_duration_seconds', 0):.2f}s",
        t("loadtest.detail_duration"),
    )
    table.add_row(
        t("loadtest.metric_throughput"),
        f"{metrics.get('overall_throughput', 0):.2f} {t('loadtest.tasks_per_sec')}",
        t("loadtest.detail_throughput"),
    )
    table.add_row(
        t("loadtest.metric_failure_rate"),
        f"{metrics.get('failure_rate_percent', 0):.1f}%",
        t("loadtest.detail_failure_rate"),
    )

    console.print(table)

    # Show performance analysis if available
    analysis = result.get("analysis", {})
    if analysis and detailed:
        _display_performance_analysis(analysis)

    # Show performance summary
    perf_summary = result.get("performance_summary", t("loadtest.no_summary"))
    console.print(f"\n[bold yellow]{t('loadtest.perf_summary')}[/bold yellow]")
    console.print(f"   {perf_summary}")

    # Show recommendations if available
    recommendations = analysis.get("recommendations", []) if analysis else []
    if recommendations:
        translated_recs = _t_recommendations(recommendations)
        console.print(f"\n[bold blue]{t('loadtest.recommendations')}[/bold blue]")
        for i, rec in enumerate(translated_recs, 1):
            console.print(f"   {i}. {rec}")


def _display_error_result(result: dict[str, Any], status: str) -> None:
    """Display results for failed or timed out load tests."""

    test_id = result.get("test_id", "unknown")
    error = result.get("error", "Unknown error")
    partial_info = result.get("partial_info", "")

    if status == "timed_out":
        console.print(
            Panel(
                f"[bold red]{t('loadtest.timed_out_title')}[/bold red]\n\n"
                f"[cyan]{t('loadtest.test_id_label')}[/cyan] {test_id}\n"
                f"[cyan]{t('loadtest.error_label')}[/cyan] {error}\n\n"
                f"[yellow]{t('loadtest.what_this_means')}[/yellow]\n"
                f"{t('loadtest.timeout_explanation')}\n\n"
                f"[blue]{t('loadtest.to_investigate')}[/blue]\n"
                f"• {t('loadtest.tip_check_logs')}\n"
                f"• {t('loadtest.tip_smaller_batch')}\n"
                f"• {t('loadtest.tip_check_metrics')}",
                title=t("loadtest.analysis_panel"),
                border_style="red",
            )
        )

        if partial_info:
            console.print(f"\n[dim]{partial_info}[/dim]")

    elif status == "failed":
        console.print(
            Panel(
                f"[bold red]{t('loadtest.failed_title')}[/bold red]\n\n"
                f"[cyan]{t('loadtest.test_id_label')}[/cyan] {test_id}\n"
                f"[cyan]{t('loadtest.error_label')}[/cyan] {error}\n\n"
                f"[blue]{t('loadtest.next_steps')}[/blue]\n"
                f"• {t('loadtest.tip_check_worker_logs')}\n"
                f"• {t('loadtest.tip_verify_queue')}\n"
                f"• {t('loadtest.tip_try_smaller')}",
                title=t("loadtest.analysis_panel"),
                border_style="red",
            )
        )

    # Show basic troubleshooting info
    console.print(f"\n[bold yellow]{t('loadtest.troubleshooting')}[/bold yellow]")
    console.print(f"   1. {t('loadtest.troubleshoot_1')}")
    console.print(f"   2. {t('loadtest.troubleshoot_2', app='nwvault-legacy')}")
    console.print(f"   3. {t('loadtest.troubleshoot_3', app='nwvault-legacy')}")


def _display_performance_analysis(analysis: dict[str, Any]) -> None:
    """Display detailed performance analysis."""

    perf_analysis = analysis.get("performance_analysis", {})
    validation = analysis.get("validation_status", {})

    # Performance ratings table
    perf_table = Table(
        title=t("loadtest.perf_analysis_title"),
        show_header=True,
        header_style="bold blue",
    )
    perf_table.add_column(t("loadtest.aspect_column"), style="cyan")
    perf_table.add_column(t("loadtest.rating_column"), style="bold")
    perf_table.add_column(t("loadtest.description_column"), style="dim")

    # Add performance ratings with color coding
    throughput_rating = perf_analysis.get("throughput_rating", "unknown")
    throughput_color = _get_rating_color(throughput_rating)
    perf_table.add_row(
        t("loadtest.aspect_throughput"),
        f"[{throughput_color}]{_t_rating(throughput_rating)}[/{throughput_color}]",
        t("loadtest.desc_throughput"),
    )

    efficiency_rating = perf_analysis.get("efficiency_rating", "unknown")
    efficiency_color = _get_rating_color(efficiency_rating)
    perf_table.add_row(
        t("loadtest.aspect_efficiency"),
        f"[{efficiency_color}]{_t_rating(efficiency_rating)}[/{efficiency_color}]",
        t("loadtest.desc_efficiency"),
    )

    queue_pressure = perf_analysis.get("queue_pressure", "unknown")
    pressure_color = (
        "red"
        if queue_pressure == "high"
        else "yellow"
        if queue_pressure == "medium"
        else "green"
    )
    perf_table.add_row(
        t("loadtest.aspect_queue_pressure"),
        f"[{pressure_color}]{_t_pressure(queue_pressure)}[/{pressure_color}]",
        t("loadtest.desc_queue_pressure"),
    )

    console.print(perf_table)

    # Validation status
    if validation:
        console.print(f"\n[bold green]{t('loadtest.test_validation')}[/bold green]")
        console.print(
            f"   {t('loadtest.validation_type')} "
            f"{_t_validation(validation.get('test_type_verified', 'unknown'))}"
        )
        console.print(
            f"   {t('loadtest.validation_metrics')} "
            f"{_t_validation(validation.get('expected_metrics_present', 'unknown'))}"
        )
        console.print(
            f"   {t('loadtest.validation_signature')} "
            f"{_t_validation(validation.get('performance_signature_match', 'unknown'))}"
        )


def _get_rating_color(rating: str) -> str:
    """Get color for performance rating."""
    color_map = {
        "excellent": "green",
        "good": "blue",
        "fair": "yellow",
        "poor": "red",
        "unknown": "dim",
    }
    return color_map.get(rating, "dim")


if __name__ == "__main__":
    app()
