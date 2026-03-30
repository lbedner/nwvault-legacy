"""
Vault archive CLI commands.

Download, import, and manage the NWVault legacy archive data.
"""

import asyncio
from pathlib import Path

from rich.console import Console
from rich.table import Table
import typer

app = typer.Typer(
    name="vault",
    help="NWVault archive management commands.",
    no_args_is_help=True,
)
console = Console()

ARCHIVE_DIR = Path("archive")


def _ensure_db() -> None:
    """Ensure vault tables exist in the database."""
    from app.core.db import init_database
    import app.models.vault  # noqa: F401 — register models

    init_database()


@app.command("download-xml")
def download_xml() -> None:
    """Download XML metadata files from rolovault (~170MB).

    This is the fast first step — pulls all *_data.xml files
    containing entry metadata, comments, scores, and file listings.
    """
    from app.services.vault.downloader import download_data_xmls

    console.print(
        "[bold cyan]Downloading XML metadata from rolovault...[/bold cyan]"
    )
    count = asyncio.run(download_data_xmls(ARCHIVE_DIR))
    console.print(
        f"[bold green]Done![/bold green] "
        f"Downloaded {count} XML data files to {ARCHIVE_DIR}/",
    )


@app.command("import")
def import_xml(
    category: str | None = typer.Option(
        None, "--category", "-c",
        help="Import only a specific category (e.g., modules, hakpaks)",
    ),
) -> None:
    """Parse downloaded XML files and import entries into the database."""
    _ensure_db()
    from app.core.db import db_session
    from app.services.vault.importer import (
        NWN1_CATEGORIES,
        NWN2_CATEGORIES,
        import_category,
        parse_xml_file,
    )

    console.print("[bold cyan]Importing vault data into database...[/bold cyan]")

    results: dict[str, int] = {}

    with db_session() as session:
        # Build category list
        categories: list[tuple[str, str]] = []
        if category:
            # Determine which game this category belongs to
            if category in NWN1_CATEGORIES:
                categories.append(("nwn1", category))
            elif category in NWN2_CATEGORIES:
                categories.append(("nwn2", category))
            else:
                console.print(f"[red]Unknown category: {category}[/red]")
                raise typer.Exit(1)
        else:
            for slug in NWN1_CATEGORIES:
                categories.append(("nwn1", slug))
            for slug in NWN2_CATEGORIES:
                categories.append(("nwn2", slug))

        for game, slug in categories:
            xml_path = ARCHIVE_DIR / game / f"{slug}_data.xml"
            if not xml_path.exists():
                continue

            console.print(f"  Parsing {game}/{slug}_data.xml...", end="")
            entries = parse_xml_file(xml_path)
            count = import_category(
                session, game, slug, entries, ARCHIVE_DIR,
            )
            results[f"{game}/{slug}"] = count
            console.print(f" [green]{count} entries[/green]")

    total = sum(results.values())
    console.print(
        f"\n[bold green]Import complete![/bold green] "
        f"{total} entries across {len(results)} categories",
    )


@app.command("download")
def download_archive(
    category: str | None = typer.Option(
        None, "--category", "-c",
        help="Download only a specific category",
    ),
    workers: int = typer.Option(
        10, "--workers", "-w",
        help="Max concurrent downloads",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n",
        help="Show what would be downloaded without downloading",
    ),
) -> None:
    """Download HTML pages, screenshots, and assets from rolovault.

    Excludes mod binary files (.zip, .7z, .hak, etc.) by default.
    Supports resume — skips files that already exist locally.
    """
    from app.services.vault.downloader import (
        USER_AGENT,
        fetch_listing,
        filter_files,
        get_download_stats,
    )
    from app.services.vault.downloader import (
        download_archive as do_download,
    )

    async def run() -> None:
        import httpx

        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        ) as client:
            console.print(
                "[bold cyan]Fetching file listing...[/bold cyan]"
            )
            listing = await fetch_listing(client)
            files = filter_files(listing, category=category)

            if dry_run:
                stats = get_download_stats(files)
                console.print(
                    f"\n[bold]Would download "
                    f"{len(files)} files:[/bold]\n"
                )
                table = Table(title="Files by Extension")
                table.add_column("Extension", style="cyan")
                table.add_column("Count", style="green", justify="right")
                for ext, count in stats.items():
                    table.add_row(ext, str(count))
                console.print(table)
                return

        console.print(
            f"[bold cyan]Downloading {len(files)} files "
            f"({workers} concurrent)...[/bold cyan]"
        )
        result = await do_download(
            ARCHIVE_DIR,
            category=category,
            max_concurrent=workers,
        )
        console.print(
            f"\n[bold green]Download complete![/bold green]\n"
            f"  Downloaded: {result['downloaded']}\n"
            f"  Skipped:    {result['skipped']}\n"
            f"  Failed:     {result['failed']}\n"
            f"  Total:      {result['total']}",
        )

    asyncio.run(run())


@app.command("fix-html")
def fix_html() -> None:
    """Fix broken asset URLs in downloaded HTML files.

    Rewrites dead vnmedia.ign.com and vaultnap.ign.com URLs to
    local /vault/assets/ paths, and fixes View.php links.
    """
    from app.services.vault.html_fixer import fix_all_html

    if not ARCHIVE_DIR.exists():
        console.print(
            "[red]Archive directory not found. "
            "Run 'vault download' first.[/red]"
        )
        raise typer.Exit(1)

    console.print(
        "[bold cyan]Fixing broken asset URLs in HTML files...[/bold cyan]"
    )
    stats = fix_all_html(ARCHIVE_DIR)
    console.print(
        f"\n[bold green]Done![/bold green]\n"
        f"  Files processed: {stats['total_files']}\n"
        f"  Files modified:  {stats['files_modified']}\n"
        f"  URLs rewritten:  {stats['total_rewrites']}",
    )


@app.command("stats")
def vault_stats() -> None:
    """Show statistics about the local archive and database."""
    # Archive stats
    console.print("[bold]Archive Directory:[/bold]")
    if ARCHIVE_DIR.exists():
        html_count = len(list(ARCHIVE_DIR.rglob("*.html")))
        xml_count = len(list(ARCHIVE_DIR.rglob("*.xml")))
        img_count = len(
            list(ARCHIVE_DIR.rglob("*.jpg"))
            + list(ARCHIVE_DIR.rglob("*.png"))
            + list(ARCHIVE_DIR.rglob("*.gif"))
        )
        total_size = sum(
            f.stat().st_size
            for f in ARCHIVE_DIR.rglob("*")
            if f.is_file()
        )
        size_mb = total_size / (1024 * 1024)

        console.print(f"  Path:       {ARCHIVE_DIR.resolve()}")
        console.print(f"  Size:       {size_mb:.1f} MB")
        console.print(f"  HTML files: {html_count}")
        console.print(f"  XML files:  {xml_count}")
        console.print(f"  Images:     {img_count}")
    else:
        console.print(
            "  [yellow]Not downloaded yet. "
            "Run 'vault download-xml' to start.[/yellow]"
        )

    # Database stats
    console.print("\n[bold]Database:[/bold]")
    try:
        from sqlmodel import Session, func, select

        from app.core.db import engine
        from app.models.vault import (
            VaultCategory,
            VaultComment,
            VaultEntry,
        )

        with Session(engine) as session:
            entries = session.exec(
                select(func.count()).select_from(VaultEntry)
            ).one()
            comments = session.exec(
                select(func.count()).select_from(VaultComment)
            ).one()
            cats = session.exec(
                select(func.count()).select_from(VaultCategory)
            ).one()
            nwn1 = session.exec(
                select(func.count())
                .select_from(VaultEntry)
                .where(VaultEntry.game == "nwn1")
            ).one()
            nwn2 = session.exec(
                select(func.count())
                .select_from(VaultEntry)
                .where(VaultEntry.game == "nwn2")
            ).one()

            console.print(f"  Categories: {cats}")
            console.print(f"  Entries:    {entries} (NWN1: {nwn1}, NWN2: {nwn2})")
            console.print(f"  Comments:   {comments}")

    except Exception as e:
        console.print(
            f"  [yellow]Database not initialized: {e}[/yellow]"
        )


@app.command("pipeline")
def run_pipeline() -> None:
    """Run the full import pipeline: download XMLs, import, done.

    This is the quickest way to get data into the system.
    Downloads ~170MB of XML metadata, then imports into the database.
    """
    console.print(
        "[bold cyan]Running full vault import pipeline...[/bold cyan]\n"
    )

    # Step 1: Download XMLs
    console.print("[bold]Step 1/2: Downloading XML metadata...[/bold]")
    from app.services.vault.downloader import download_data_xmls

    count = asyncio.run(download_data_xmls(ARCHIVE_DIR))
    console.print(f"  [green]{count} XML files downloaded[/green]\n")

    # Step 2: Import to DB
    console.print("[bold]Step 2/2: Importing to database...[/bold]")
    _ensure_db()
    from app.services.vault.importer import import_all

    results = import_all(ARCHIVE_DIR)
    total = sum(results.values())
    console.print(f"  [green]{total} entries imported[/green]\n")

    # Summary
    table = Table(title="Import Summary")
    table.add_column("Category", style="cyan")
    table.add_column("Entries", style="green", justify="right")
    for cat, cnt in sorted(results.items()):
        if cnt > 0:
            table.add_row(cat, str(cnt))
    console.print(table)

    console.print(
        "\n[bold green]Pipeline complete![/bold green] "
        "Run 'vault stats' to see your data.",
    )
