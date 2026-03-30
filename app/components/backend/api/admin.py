"""Admin API endpoints for managing vault imports via worker queues."""

from pathlib import Path

from fastapi import APIRouter, Query

from app.components.worker.events import publish_event
from app.components.worker.pools import get_queue_pool
from app.core.log import logger
from app.services.vault.importer import (
    NWN1_CATEGORIES,
    NWN2_CATEGORIES,
)

router = APIRouter()

ARCHIVE_DIR = Path("archive")


@router.post("/import/pipeline")
async def trigger_pipeline() -> dict:
    """Run the full vault pipeline via workers.

    Enqueues: download_xml_data to vault_download,
    then import_category jobs to vault_import,
    download_category jobs to vault_download,
    and fix_html_category jobs to vault_fix.
    """
    all_categories: list[tuple[str, str]] = []
    for slug in NWN1_CATEGORIES:
        all_categories.append(("nwn1", slug))
    for slug in NWN2_CATEGORIES:
        all_categories.append(("nwn2", slug))

    jobs_enqueued = 0

    # Enqueue XML metadata download
    dl_pool, dl_queue = await get_queue_pool("vault_download")
    job = await dl_pool.enqueue_job(
        "download_xml_data", _queue_name=dl_queue,
    )
    if job:
        await publish_event(
            dl_pool, "job.enqueued", "vault_download",
            {"job_id": job.job_id, "task": "download_xml_data"},
        )
        jobs_enqueued += 1

    # Enqueue per-category jobs
    imp_pool, imp_queue = await get_queue_pool("vault_import")
    fix_pool, fix_queue = await get_queue_pool("vault_fix")

    for game, slug in all_categories:
        # Import
        job = await imp_pool.enqueue_job(
            "import_category",
            _queue_name=imp_queue,
            game=game,
            category=slug,
        )
        if job:
            jobs_enqueued += 1

        # Download HTML + images
        job = await dl_pool.enqueue_job(
            "download_category",
            _queue_name=dl_queue,
            game=game,
            category=slug,
        )
        if job:
            jobs_enqueued += 1

        # Fix HTML
        job = await fix_pool.enqueue_job(
            "fix_html_category",
            _queue_name=fix_queue,
            game=game,
            category=slug,
        )
        if job:
            jobs_enqueued += 1

    await dl_pool.aclose()
    await imp_pool.aclose()
    await fix_pool.aclose()

    logger.info(
        f"Pipeline enqueued {jobs_enqueued} jobs "
        f"across {len(all_categories)} categories"
    )

    return {
        "status": "enqueued",
        "jobs_enqueued": jobs_enqueued,
        "categories": len(all_categories),
        "queues": [
            "vault_download",
            "vault_import",
            "vault_fix",
        ],
    }


@router.post("/import/download-xmls")
async def trigger_xml_download() -> dict:
    """Enqueue XML metadata download to vault_download worker."""
    pool, queue_name = await get_queue_pool("vault_download")
    job = await pool.enqueue_job(
        "download_xml_data", _queue_name=queue_name,
    )
    if job:
        await publish_event(
            pool, "job.enqueued", "vault_download",
            {"job_id": job.job_id, "task": "download_xml_data"},
        )
    await pool.aclose()

    return {
        "status": "enqueued",
        "job_id": job.job_id if job else None,
        "queue": "vault_download",
    }


@router.post("/import/xml")
async def trigger_xml_import(
    game: str | None = Query(
        None, description="Limit to game: nwn1, nwn2",
    ),
    category: str | None = Query(
        None, description="Limit to category slug",
    ),
) -> dict:
    """Enqueue XML import jobs to vault_import worker.

    With no filters, enqueues one job per category (~37 jobs).
    """
    pool, queue_name = await get_queue_pool("vault_import")

    categories: list[tuple[str, str]] = []
    if game and category:
        categories.append((game, category))
    elif game:
        cat_map = (
            NWN1_CATEGORIES if game == "nwn1" else NWN2_CATEGORIES
        )
        for slug in cat_map:
            categories.append((game, slug))
    else:
        for slug in NWN1_CATEGORIES:
            categories.append(("nwn1", slug))
        for slug in NWN2_CATEGORIES:
            categories.append(("nwn2", slug))

    jobs_enqueued = 0
    for g, slug in categories:
        job = await pool.enqueue_job(
            "import_category",
            _queue_name=queue_name,
            game=g,
            category=slug,
        )
        if job:
            jobs_enqueued += 1

    await pool.aclose()

    return {
        "status": "enqueued",
        "jobs_enqueued": jobs_enqueued,
        "queue": "vault_import",
    }


@router.post("/import/download")
async def trigger_download(
    game: str | None = Query(
        None, description="Limit to game: nwn1, nwn2",
    ),
    category: str | None = Query(
        None, description="Limit to category slug",
    ),
) -> dict:
    """Enqueue HTML/image download jobs to vault_download worker."""
    pool, queue_name = await get_queue_pool("vault_download")

    categories: list[tuple[str, str]] = []
    if game and category:
        categories.append((game, category))
    elif game:
        cat_map = (
            NWN1_CATEGORIES if game == "nwn1" else NWN2_CATEGORIES
        )
        for slug in cat_map:
            categories.append((game, slug))
    else:
        for slug in NWN1_CATEGORIES:
            categories.append(("nwn1", slug))
        for slug in NWN2_CATEGORIES:
            categories.append(("nwn2", slug))

    jobs_enqueued = 0
    for g, slug in categories:
        job = await pool.enqueue_job(
            "download_category",
            _queue_name=queue_name,
            game=g,
            category=slug,
        )
        if job:
            jobs_enqueued += 1

    await pool.aclose()

    return {
        "status": "enqueued",
        "jobs_enqueued": jobs_enqueued,
        "queue": "vault_download",
    }


@router.post("/import/fix-html")
async def trigger_html_fix(
    game: str | None = Query(
        None, description="Limit to game: nwn1, nwn2",
    ),
    category: str | None = Query(
        None, description="Limit to category slug",
    ),
) -> dict:
    """Enqueue HTML fix jobs to vault_fix worker."""
    pool, queue_name = await get_queue_pool("vault_fix")

    categories: list[tuple[str, str]] = []
    if game and category:
        categories.append((game, category))
    elif game:
        cat_map = (
            NWN1_CATEGORIES if game == "nwn1" else NWN2_CATEGORIES
        )
        for slug in cat_map:
            categories.append((game, slug))
    else:
        for slug in NWN1_CATEGORIES:
            categories.append(("nwn1", slug))
        for slug in NWN2_CATEGORIES:
            categories.append(("nwn2", slug))

    jobs_enqueued = 0
    for g, slug in categories:
        job = await pool.enqueue_job(
            "fix_html_category",
            _queue_name=queue_name,
            game=g,
            category=slug,
        )
        if job:
            jobs_enqueued += 1

    await pool.aclose()

    return {
        "status": "enqueued",
        "jobs_enqueued": jobs_enqueued,
        "queue": "vault_fix",
    }


@router.post("/import/scrape-reviews")
async def trigger_review_scrape(
    game: str | None = Query(
        None, description="Limit to game: nwn1, nwn2",
    ),
    category: str | None = Query(
        None, description="Limit to category slug",
    ),
    min_votes: int = Query(
        0, description="Only scrape entries with this many votes",
    ),
) -> dict:
    """Enqueue review scrape orchestrators to vault_download.

    Each orchestrator checks the DB for entries missing reviews,
    then enqueues one scrape_review job per entry.
    """
    pool, queue_name = await get_queue_pool("vault_download")

    categories: list[tuple[str, str]] = []
    if game and category:
        categories.append((game, category))
    elif game:
        cat_map = (
            NWN1_CATEGORIES if game == "nwn1" else NWN2_CATEGORIES
        )
        for slug in cat_map:
            categories.append((game, slug))
    else:
        for slug in NWN1_CATEGORIES:
            categories.append(("nwn1", slug))
        for slug in NWN2_CATEGORIES:
            categories.append(("nwn2", slug))

    jobs_enqueued = 0
    for g, slug in categories:
        job = await pool.enqueue_job(
            "enqueue_review_scrape",
            _queue_name=queue_name,
            game=g,
            category=slug,
            min_votes=min_votes,
        )
        if job:
            jobs_enqueued += 1

    await pool.aclose()

    return {
        "status": "enqueued",
        "orchestrator_jobs": jobs_enqueued,
        "queue": "vault_download",
    }


@router.get("/archive/stats")
def archive_stats() -> dict:
    """Get statistics about the local archive directory."""
    if not ARCHIVE_DIR.exists():
        return {
            "exists": False,
            "message": "Archive directory not found. "
            "Run download first.",
        }

    html_count = len(list(ARCHIVE_DIR.rglob("*.html")))
    xml_count = len(list(ARCHIVE_DIR.rglob("*.xml")))
    jpg_count = len(list(ARCHIVE_DIR.rglob("*.jpg")))
    png_count = len(list(ARCHIVE_DIR.rglob("*.png")))

    total_size = sum(
        f.stat().st_size
        for f in ARCHIVE_DIR.rglob("*")
        if f.is_file()
    )

    return {
        "exists": True,
        "total_size_mb": round(total_size / (1024 * 1024), 1),
        "html_files": html_count,
        "xml_files": xml_count,
        "jpg_files": jpg_count,
        "png_files": png_count,
    }
