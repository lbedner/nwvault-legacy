"""Download archive files from neverwintervault.org/rolovault."""

import asyncio
from pathlib import Path

import httpx

from app.core.log import logger

ROLOVAULT_BASE = "https://neverwintervault.org/rolovault"
LISTING_URL = f"{ROLOVAULT_BASE}/projects/listing.txt"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# File extensions to download
INCLUDE_EXTENSIONS = {
    ".html", ".htm", ".xml", ".jpg", ".jpeg", ".png", ".gif",
    ".bmp", ".css", ".js", ".txt", ".ini",
}

# File extensions to skip (mod binaries)
EXCLUDE_EXTENSIONS = {
    ".zip", ".7z", ".rar", ".exe", ".msi", ".gz", ".tgz", ".tar",
    ".bz2", ".hak", ".mod", ".erf", ".nwm", ".tlk", ".bif", ".key",
    ".wav", ".mp3", ".bmu", ".nss", ".ncs", ".2da",
}


async def fetch_listing(client: httpx.AsyncClient) -> list[str]:
    """Fetch the full file listing from rolovault."""
    resp = await client.get(LISTING_URL)
    resp.raise_for_status()
    lines = resp.text.strip().splitlines()
    # Lines look like: ./nwn1/modules/1/index.html
    return [line.strip() for line in lines if line.strip()]


def filter_files(
    listing: list[str],
    category: str | None = None,
) -> list[str]:
    """Filter listing to only files we want to download.

    Args:
        listing: Full file listing from rolovault.
        category: Optional category filter (e.g., "modules", "hakpaks").

    Returns:
        Filtered list of relative file paths.
    """
    filtered = []
    for path in listing:
        suffix = Path(path).suffix.lower()

        # Skip excluded extensions
        if suffix in EXCLUDE_EXTENSIONS:
            continue

        # Skip extensionless paths (directories in the listing)
        if not suffix:
            continue

        # Only include known extensions
        if suffix not in INCLUDE_EXTENSIONS:
            continue

        # Skip if not matching requested category
        if category and f"/{category}/" not in path:
            continue

        filtered.append(path)

    return filtered


def get_download_stats(listing: list[str]) -> dict[str, int]:
    """Get download statistics by file extension."""
    stats: dict[str, int] = {}
    for path in listing:
        suffix = Path(path).suffix.lower() or "(no ext)"
        stats[suffix] = stats.get(suffix, 0) + 1
    return dict(sorted(stats.items(), key=lambda x: -x[1]))


async def download_file(
    client: httpx.AsyncClient,
    relative_path: str,
    archive_dir: Path,
) -> bool:
    """Download a single file from rolovault.

    Args:
        client: HTTP client with proper headers.
        relative_path: Path relative to rolovault/projects/
            (e.g., "./nwn1/modules/1/index.html").
        archive_dir: Local directory to save files.

    Returns:
        True if file was downloaded (or already exists), False on error.
    """
    # Normalize the path
    clean_path = relative_path.lstrip("./")
    local_path = archive_dir / clean_path

    # Skip if already downloaded
    if local_path.exists() and local_path.stat().st_size > 0:
        return True

    url = f"{ROLOVAULT_BASE}/projects/{clean_path}"

    try:
        resp = await client.get(url)
        resp.raise_for_status()

        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(resp.content)
        return True

    except httpx.HTTPStatusError as e:
        if e.response.status_code != 404:
            logger.warning(f"HTTP {e.response.status_code} downloading {url}")
        return False
    except Exception as e:
        logger.warning(f"Error downloading {url}: {e}")
        return False


async def download_archive(
    archive_dir: Path,
    category: str | None = None,
    max_concurrent: int = 10,
    progress_callback: object | None = None,
) -> dict[str, int]:
    """Download archive files from rolovault.

    Args:
        archive_dir: Local directory to save files.
        category: Optional category filter.
        max_concurrent: Max concurrent downloads.
        progress_callback: Optional async callable(completed, total, path) for progress.

    Returns:
        Stats dict with counts: downloaded, skipped, failed, total.
    """
    archive_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        logger.info("Fetching file listing from rolovault...")
        listing = await fetch_listing(client)
        logger.info(f"Found {len(listing)} total files in listing")

        files = filter_files(listing, category=category)
        logger.info(f"Filtered to {len(files)} files to download")

        stats = {"downloaded": 0, "skipped": 0, "failed": 0, "total": len(files)}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_with_semaphore(path: str) -> None:
            async with semaphore:
                clean_path = path.lstrip("./")
                local_path = archive_dir / clean_path

                if local_path.exists() and local_path.stat().st_size > 0:
                    stats["skipped"] += 1
                else:
                    success = await download_file(client, path, archive_dir)
                    if success:
                        stats["downloaded"] += 1
                    else:
                        stats["failed"] += 1

                completed = stats["downloaded"] + stats["skipped"] + stats["failed"]
                if progress_callback and callable(progress_callback):
                    await progress_callback(completed, stats["total"], path)

                if completed % 500 == 0:
                    logger.info(
                        f"Progress: {completed}/{stats['total']} "
                        f"(downloaded={stats['downloaded']}, "
                        f"skipped={stats['skipped']}, "
                        f"failed={stats['failed']})"
                    )

        tasks = [download_with_semaphore(f) for f in files]
        await asyncio.gather(*tasks)

        logger.info(
            f"Download complete: {stats['downloaded']} downloaded, "
            f"{stats['skipped']} skipped, {stats['failed']} failed"
        )
        return stats


async def download_data_xmls(archive_dir: Path) -> int:
    """Download just the *_data.xml category files (fast metadata-only import).

    Returns:
        Number of XML files downloaded.
    """
    archive_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    nwn1_categories = [
        "artwork", "characters", "community_news", "creatures", "gameworld",
        "hakpaks", "ideas", "links", "models", "moduleideas", "modules",
        "movies", "other", "portraits", "prefabs", "screenshots", "scripts",
        "sounds", "textures",
    ]

    nwn2_categories = [
        "nwn2characters", "nwn2gameworlds", "nwn2hakpakscombined",
        "nwn2hakpaksmodulespecific", "nwn2hakpaksoriginal", "nwn2ideas",
        "nwn2links", "nwn2models", "nwn2modulesenglish",
        "nwn2modulesinternational", "nwn2movies", "nwn2other", "nwn2plugins",
        "nwn2portraits", "nwn2prefabareas", "nwn2prefabplaceables", "nwn2pwc",
        "nwn2scripts", "nwn2strategies", "nwn2textures", "nwn2tools",
        "nwn2tutorials", "nwn2ui", "nwn2visualeffects",
    ]

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        for cat in nwn1_categories:
            url = f"{ROLOVAULT_BASE}/projects/nwn1/{cat}_data.xml"
            local_path = archive_dir / "nwn1" / f"{cat}_data.xml"
            if local_path.exists() and local_path.stat().st_size > 0:
                count += 1
                continue
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(resp.content)
                logger.info(f"Downloaded {cat}_data.xml ({len(resp.content)} bytes)")
                count += 1
            except Exception as e:
                logger.warning(f"Failed to download {cat}_data.xml: {e}")

        for cat in nwn2_categories:
            url = f"{ROLOVAULT_BASE}/projects/nwn2/{cat}_data.xml"
            local_path = archive_dir / "nwn2" / f"{cat}_data.xml"
            if local_path.exists() and local_path.stat().st_size > 0:
                count += 1
                continue
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(resp.content)
                logger.info(f"Downloaded {cat}_data.xml ({len(resp.content)} bytes)")
                count += 1
            except Exception as e:
                logger.warning(f"Failed to download {cat}_data.xml: {e}")

    return count
