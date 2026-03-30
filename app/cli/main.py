"""
Main CLI application entry point.

Command-line interface for nwvault-legacy management tasks.
"""

import asyncio
import importlib
import inspect
import sys
from typing import TYPE_CHECKING

import click
import typer

from app.cli import docs, health
import app.cli._i18n_click  # noqa: F401 — translate Click's built-in --help text
from app.i18n import detect_locale, lazy_t, set_locale, t
from app.i18n.locales import AVAILABLE_LOCALES

if TYPE_CHECKING:
    pass

app = typer.Typer(
    name="nwvault-legacy",
    help=lazy_t("main.help"),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)


@app.callback()
def main_callback(
    lang: str | None = typer.Option(
        None,
        "--lang",
        help=lazy_t("main.opt_lang"),
        envvar="NWVAULT_LEGACY_LANG",
    ),
) -> None:
    normalized = lang.lower().replace("-", "_").split("_")[0] if lang else None
    if normalized and normalized not in AVAILABLE_LOCALES:
        typer.secho(
            t("main.unsupported_lang", lang=lang, available=", ".join(sorted(AVAILABLE_LOCALES))),
            fg="red",
            err=True,
        )
        raise typer.Exit(1)
    set_locale(lang if lang else detect_locale())


# Register sub-commands
app.add_typer(health.app, name="health")
app.add_typer(docs.app, name="docs")

# Register vault archive management commands
try:
    vault_module = importlib.import_module("app.cli.vault")
    app.add_typer(vault_module.app, name="vault")
except ImportError:
    pass

# Conditionally register load-test command if worker components are available
try:
    load_test_module = importlib.import_module("app.cli.load_test")
    app.add_typer(load_test_module.app, name="load-test")
except ImportError:
    # Worker components not available, skip load-test commands
    pass

# Conditionally register tasks command if scheduler components are available
try:
    tasks_module = importlib.import_module("app.cli.tasks")
    app.add_typer(tasks_module.app, name="tasks")
except (ImportError, AttributeError):
    # Scheduler components not available or tasks module incomplete, skip tasks commands
    pass

# Conditionally register auth command if auth service is available
try:
    auth_module = importlib.import_module("app.cli.auth")
    app.add_typer(auth_module.app, name="auth")
except ImportError:
    # Auth service not available, skip auth commands
    pass

# Conditionally register ai command if ai service is available
try:
    ai_module = importlib.import_module("app.cli.ai")
    app.add_typer(ai_module.app, name="ai")
except ImportError:
    # AI service not available, skip ai commands
    pass

# Conditionally register comms command if comms service is available
try:
    comms_module = importlib.import_module("app.cli.comms")
    app.add_typer(comms_module.app, name="comms")
except ImportError:
    # Comms service not available, skip comms commands
    pass

# Conditionally register rag command if ai_rag is enabled
try:
    rag_module = importlib.import_module("app.cli.rag")
    app.add_typer(rag_module.app, name="rag")
except ImportError:
    # RAG not available, skip rag commands
    pass

# Conditionally register llm command if ai service is available
try:
    llm_module = importlib.import_module("app.cli.llm")
    app.add_typer(llm_module.app, name="llm")
except ImportError:
    # LLM ETL service not available, skip llm commands
    pass


def main() -> None:
    """Entry point for the CLI application."""
    try:
        result = app(standalone_mode=False)
        # Handle async commands - standalone_mode=False returns coroutines unawaited
        if inspect.iscoroutine(result):
            asyncio.run(result)
    except click.exceptions.UsageError as e:
        # Show help automatically on usage errors instead of just "try --help"
        if e.ctx is not None:
            click.echo(e.ctx.get_help())
            click.echo()
        click.echo(f"Error: {e.format_message()}", err=True)
        sys.exit(2)
    except click.exceptions.Abort:
        # User cancelled (e.g., Ctrl+C)
        sys.exit(1)
    except click.exceptions.Exit as e:
        # Normal exit requested (e.g., after showing error message)
        sys.exit(e.exit_code)
    except SystemExit:
        # Re-raise system exits (normal exit codes)
        raise


if __name__ == "__main__":
    main()
