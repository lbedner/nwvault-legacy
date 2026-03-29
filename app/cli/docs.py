"""Documentation links CLI command.

Displays documentation URLs for installed components and services.
"""

from pathlib import Path

import typer
from app.i18n import lazy_t, t
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(name="docs", help=lazy_t("docs.help"), invoke_without_command=True)
console = Console()

# Base URL for Aegis Stack documentation
AEGIS_BASE = "https://lbedner.github.io/aegis-stack"

# Documentation config: name -> (aegis_path, external_url, description)
# Components
COMPONENT_DOCS: dict[str, tuple[str, str | None, str]] = {
    "backend": ("/components/webserver/", "https://fastapi.tiangolo.com/", "FastAPI"),
    "frontend": ("/components/frontend/", "https://flet.dev/", "Flet"),
    "scheduler": (
        "/components/scheduler/",
        "https://apscheduler.readthedocs.io/",
        "APScheduler",
    ),
    "worker": (
        "/components/worker/",
        "https://arq-docs.helpmanual.io/",
        "arq",
    ),
    "database": (
        "/components/database/",
        "https://sqlmodel.tiangolo.com/",
        "SQLModel",
    ),
}

# Services
SERVICE_DOCS: dict[str, tuple[str, str | None, str]] = {
    "auth": ("/services/auth/", None, "Authentication"),
    "ai": ("/services/ai/", None, "AI Service"),
    "comms": ("/services/comms/", None, "Communications"),
}


def _get_app_path() -> Path:
    """Get the app directory path."""
    return Path(__file__).parent.parent


def _detect_installed() -> tuple[list[str], list[str]]:
    """Detect installed components and services by checking directories.

    Returns:
        Tuple of (components, services) lists.
    """
    app_path = _get_app_path()

    # Check components
    components = ["backend", "frontend"]  # Always present
    components_dir = app_path / "components"

    if (components_dir / "scheduler").exists():
        components.append("scheduler")
    if (components_dir / "worker").exists():
        components.append("worker")

    # Check if database is present (models directory with actual models)
    models_dir = app_path / "models"
    if models_dir.exists():
        # Check for actual model files (not just __init__.py)
        model_files = [f for f in models_dir.glob("*.py") if f.name != "__init__.py"]
        if model_files:
            components.append("database")

    # Check services
    services: list[str] = []
    services_dir = app_path / "services"

    if (services_dir / "auth").exists():
        services.append("auth")
    if (services_dir / "ai").exists():
        services.append("ai")
    if (services_dir / "comms").exists():
        services.append("comms")

    return components, services


def _format_docs_section(
    title: str,
    items: list[str],
    docs_config: dict[str, tuple[str, str | None, str]],
) -> list[str]:
    """Format a documentation section.

    Args:
        title: Section title (e.g., "Components")
        items: List of item names to display
        docs_config: Documentation config dict

    Returns:
        List of formatted lines.
    """
    lines: list[str] = []
    lines.append(f"[bold cyan]{title}:[/bold cyan]")

    for item in items:
        if item not in docs_config:
            continue

        aegis_path, external_url, description = docs_config[item]
        lines.append(f"  [bold]{item}[/bold] ({description})")
        lines.append(f"    {t('docs.guide_label')} {AEGIS_BASE}{aegis_path}")
        if external_url:
            lines.append(f"    {t('docs.docs_label')}  {external_url}")
        lines.append("")

    return lines


@app.callback(help=lazy_t("docs.help_show"))
def show() -> None:
    components, services = _detect_installed()

    lines: list[str] = []

    # Components section
    if components:
        lines.extend(
            _format_docs_section(t("docs.components"), components, COMPONENT_DOCS)
        )

    # Services section
    if services:
        lines.extend(_format_docs_section(t("docs.services"), services, SERVICE_DOCS))

    if not lines:
        console.print(f"[yellow]{t('docs.no_detected')}[/yellow]")
        return

    # Get project name from directory
    project_name = _get_app_path().parent.name

    panel = Panel(
        "\n".join(lines).rstrip(),
        title=f"[bold]{project_name} {t('docs.documentation')}[/bold]",
        border_style="cyan",
    )
    console.print(panel)


if __name__ == "__main__":
    app()
