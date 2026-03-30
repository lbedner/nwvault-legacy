"""Worker tasks for vault archive operations.

Each task is scoped to a single category or entry for granular
progress tracking and resilience.
"""

from pathlib import Path
from typing import Any

from app.core.log import logger

ARCHIVE_DIR = Path("archive")


async def download_xml_data(ctx: dict[str, Any]) -> dict[str, Any]:
    """Download all XML metadata files from rolovault (~170MB)."""
    from app.services.vault.downloader import download_data_xmls

    logger.info("Starting XML data download from rolovault...")
    count = await download_data_xmls(ARCHIVE_DIR)
    return {"status": "completed", "files_downloaded": count}


async def import_category(
    ctx: dict[str, Any],
    game: str = "nwn1",
    category: str = "modules",
) -> dict[str, Any]:
    """Parse one category's XML and import entries into the database."""
    from app.core.db import db_session, init_database
    import app.models.vault  # noqa: F401
    from app.services.vault.importer import (
        import_category as do_import,
    )
    from app.services.vault.importer import (
        parse_xml_file,
    )

    init_database()

    xml_path = ARCHIVE_DIR / game / f"{category}_data.xml"
    if not xml_path.exists():
        return {
            "status": "skipped",
            "game": game,
            "category": category,
            "reason": "XML file not found",
        }

    logger.info(f"Parsing {game}/{category}_data.xml...")
    entries = parse_xml_file(xml_path)
    logger.info(f"Found {len(entries)} entries in {game}/{category}")

    with db_session() as session:
        count = do_import(
            session, game, category, entries, ARCHIVE_DIR,
        )

    logger.info(f"Imported {count} entries for {game}/{category}")
    return {
        "status": "completed",
        "game": game,
        "category": category,
        "entries_found": len(entries),
        "entries_imported": count,
    }


async def download_category(
    ctx: dict[str, Any],
    game: str = "nwn1",
    category: str = "modules",
    max_concurrent: int = 15,
) -> dict[str, Any]:
    """Download HTML pages and images for one category."""
    from app.services.vault.downloader import download_archive

    cat_filter = f"{game}/{category}"
    logger.info(f"Downloading archive files for {cat_filter}...")

    stats = await download_archive(
        ARCHIVE_DIR,
        category=f"{game}/{category}",
        max_concurrent=max_concurrent,
    )

    logger.info(
        f"Download {cat_filter}: "
        f"{stats['downloaded']} new, "
        f"{stats['skipped']} skipped, "
        f"{stats['failed']} failed"
    )
    return {
        "status": "completed",
        "game": game,
        "category": category,
        **stats,
    }


async def fix_html_category(
    ctx: dict[str, Any],
    game: str = "nwn1",
    category: str = "modules",
) -> dict[str, Any]:
    """Fix broken asset URLs in HTML files for one category."""
    from app.services.vault.html_fixer import fix_all_html

    cat_dir = ARCHIVE_DIR / game / category
    if not cat_dir.exists():
        return {
            "status": "skipped",
            "game": game,
            "category": category,
            "reason": "directory not found",
        }

    logger.info(f"Fixing HTML assets in {game}/{category}...")
    stats = fix_all_html(cat_dir)
    return {
        "status": "completed",
        "game": game,
        "category": category,
        **stats,
    }


async def scrape_review(
    ctx: dict[str, Any],
    entry_db_id: int = 0,
    entry_id: int = 0,
    category: str = "modules",
) -> dict[str, Any]:
    """Scrape reviews for a single entry from Wayback Machine.

    One entry = one job. If Wayback blocks, this job fails
    and arq retries it later.
    """
    from app.services.vault.review_scraper import (
        scrape_and_store_reviews,
    )

    count = await scrape_and_store_reviews(
        entry_db_id, entry_id, category,
    )

    return {
        "status": "completed",
        "entry_id": entry_id,
        "reviews_stored": count,
    }


async def enqueue_review_scrape(
    ctx: dict[str, Any],
    game: str = "nwn1",
    category: str = "modules",
    min_votes: int = 0,
) -> dict[str, Any]:
    """Orchestrator: check DB for entries missing reviews,
    enqueue one scrape_review job per entry.

    Only enqueues entries that don't already have reviews
    in the database.
    """
    from arq import ArqRedis
    from sqlmodel import Session, select

    from app.core.db import engine, init_database
    import app.models.vault  # noqa: F401
    from app.models.vault import VaultEntry, VaultReview

    init_database()

    with Session(engine) as session:
        # Get entries with votes in this category
        stmt = (
            select(VaultEntry)
            .where(
                VaultEntry.game == game,
                VaultEntry.category == category,
                VaultEntry.votes >= min_votes,
            )
            .order_by(VaultEntry.votes.desc())
        )
        entries = session.exec(stmt).all()

        # Get IDs that already have reviews in one query
        entry_ids = [e.id for e in entries]
        has_reviews_ids = set()
        if entry_ids:
            reviewed = session.exec(
                select(VaultReview.entry_id)
                .where(VaultReview.entry_id.in_(entry_ids))
                .distinct()
            ).all()
            has_reviews_ids = set(reviewed)

        to_scrape = [
            (e.id, e.entry_id, e.category)
            for e in entries
            if e.id not in has_reviews_ids
        ]

    logger.info(
        f"Review scrape {game}/{category}: "
        f"{len(to_scrape)} entries need reviews "
        f"(out of {len(entries)} with {min_votes}+ votes)"
    )

    if not to_scrape:
        return {
            "status": "completed",
            "game": game,
            "category": category,
            "jobs_enqueued": 0,
            "message": "All entries already have reviews",
        }

    # Enqueue one job per entry
    redis: ArqRedis = ctx.get("redis") or ctx.get("events_redis")
    enqueued = 0
    for db_id, entry_id, cat in to_scrape:
        await redis.enqueue_job(
            "scrape_review",
            _queue_name="arq:queue:vault_download",
            entry_db_id=db_id,
            entry_id=entry_id,
            category=cat,
        )
        enqueued += 1

    logger.info(f"Enqueued {enqueued} review scrape jobs")
    return {
        "status": "completed",
        "game": game,
        "category": category,
        "jobs_enqueued": enqueued,
    }
