"""Fix broken asset URLs in archived HTML files."""

from pathlib import Path
import re

from app.core.log import logger

# Old asset domains that are now dead
DEAD_DOMAINS = [
    "vnmedia.ign.com",
    "vaultnap.ign.com",
    "common.ignimgs.com",
]

# Local asset prefix — serves from archive/assets/ via static mount
LOCAL_ASSET_PREFIX = "/_assets"

# Wayback Machine prefix — fallback for assets not downloaded locally
WAYBACK_PREFIX = "https://web.archive.org/web/2012im_"

# URL patterns to rewrite (original dead URLs)
ASSET_PATTERN = re.compile(
    r'((?:src|href|background|BACKGROUND|SRC|HREF)=["\']?)'
    r'(https?://(?:'
    + "|".join(re.escape(d) for d in DEAD_DOMAINS)
    + r')/[^"\'\s>]+)',
    re.IGNORECASE,
)

# Also match previously-rewritten Wayback URLs so we can
# switch them to local serving on re-run
WAYBACK_ASSET_PATTERN = re.compile(
    r'((?:src|href|background|BACKGROUND|SRC|HREF)=["\']?)'
    r'https://web\.archive\.org/web/2012im_/'
    r'https?://((?:'
    + "|".join(re.escape(d) for d in DEAD_DOMAINS)
    + r')/[^"\'\s>]+)',
    re.IGNORECASE,
)

# Thumbnail URL pattern — maps Wayback thumbnail URLs to local files
# Matches: web.archive.org/web/2012im_/http://vnmedia.ign.com/
#   nwvault.ign.com/fms/images/{category}/{id}/{timestamp}_thumb.jpg
THUMB_PATTERN = re.compile(
    r'((?:src|SRC)=["\']?)'
    r'https://web\.archive\.org/web/2012im_/'
    r'https?://vnmedia\.ign\.com/nwvault\.ign\.com/'
    r'fms/images/([^/]+)/(\d+)/(\d+)_thumb\.jpg',
    re.IGNORECASE,
)

# Map fms/images category names to our archive game/category paths
_FMS_TO_ARCHIVE: dict[str, str] = {
    "modules": "nwn1/modules",
    "hakpaks": "nwn1/hakpaks",
    "scripts": "nwn1/scripts",
    "portraits": "nwn1/portraits",
    "creatures": "nwn1/creatures",
    "models": "nwn1/models",
    "prefabs": "nwn1/prefabs",
    "other": "nwn1/other",
    "movies": "nwn1/movies",
    "sounds": "nwn1/sounds",
    "textures": "nwn1/textures",
    "characters": "nwn1/characters",
    "gameworld": "nwn1/gameworld",
    "artwork": "nwn1/artwork",
    "screenshots": "nwn1/screenshots",
    "ideas": "nwn1/ideas",
    "nwn2modulesenglish": "nwn2/nwn2modulesenglish",
    "nwn2modulesinternational": "nwn2/nwn2modulesinternational",
    "nwn2hakpaksoriginal": "nwn2/nwn2hakpaksoriginal",
    "nwn2hakpakscombined": "nwn2/nwn2hakpakscombined",
    "nwn2models": "nwn2/nwn2models",
    "nwn2scripts": "nwn2/nwn2scripts",
    "nwn2other": "nwn2/nwn2other",
    "nwn2prefabareas": "nwn2/nwn2prefabareas",
    "nwn2prefabplaceables": "nwn2/nwn2prefabplaceables",
    "nwn2portraits": "nwn2/nwn2portraits",
    "nwn2tools": "nwn2/nwn2tools",
    "nwn2tutorials": "nwn2/nwn2tutorials",
    "nwn2ui": "nwn2/nwn2ui",
    "nwn2visualeffects": "nwn2/nwn2visualeffects",
    "nwn2movies": "nwn2/nwn2movies",
    "nwn2characters": "nwn2/nwn2characters",
    "nwn2gameworlds": "nwn2/nwn2gameworlds",
    "nwn2plugins": "nwn2/nwn2plugins",
}

# Map View.php view names to our archive paths
# View.php?view=Modules.Detail&id=123 → /vault/nwn1/modules/123/
_VIEW_TO_PATH: dict[str, str] = {
    # NWN1 categories
    "modules.detail": "nwn1/modules",
    "hakpaks.detail": "nwn1/hakpaks",
    "scripts.detail": "nwn1/scripts",
    "portraits.detail": "nwn1/portraits",
    "creatures.detail": "nwn1/creatures",
    "models.detail": "nwn1/models",
    "prefabs.detail": "nwn1/prefabs",
    "other.detail": "nwn1/other",
    "movies.detail": "nwn1/movies",
    "sounds.detail": "nwn1/sounds",
    "textures.detail": "nwn1/textures",
    "characters.detail": "nwn1/characters",
    "gameworld.detail": "nwn1/gameworld",
    # NWN2 categories
    "nwn2modulesenglish.detail": "nwn2/nwn2modulesenglish",
    "nwn2modulesinternational.detail": "nwn2/nwn2modulesinternational",
    "nwn2hakpaksoriginal.detail": "nwn2/nwn2hakpaksoriginal",
    "nwn2hakpakscombined.detail": "nwn2/nwn2hakpakscombined",
    "nwn2hakpaksmodulespecific.detail": "nwn2/nwn2hakpaksmodulespecific",
    "nwn2characters.detail": "nwn2/nwn2characters",
    "nwn2scripts.detail": "nwn2/nwn2scripts",
    "nwn2models.detail": "nwn2/nwn2models",
    "nwn2movies.detail": "nwn2/nwn2movies",
    "nwn2other.detail": "nwn2/nwn2other",
    "nwn2plugins.detail": "nwn2/nwn2plugins",
    "nwn2portraits.detail": "nwn2/nwn2portraits",
    "nwn2prefabareas.detail": "nwn2/nwn2prefabareas",
    "nwn2prefabplaceables.detail": "nwn2/nwn2prefabplaceables",
    "nwn2tools.detail": "nwn2/nwn2tools",
    "nwn2tutorials.detail": "nwn2/nwn2tutorials",
    "nwn2ui.detail": "nwn2/nwn2ui",
    "nwn2visualeffects.detail": "nwn2/nwn2visualeffects",
    "nwn2gameworlds.detail": "nwn2/nwn2gameworlds",
    "nwn2strategies.detail": "nwn2/nwn2strategies",
}

# Pattern for View.php detail links with entry ID
_DETAIL_LINK = re.compile(
    r'(href=["\']?)'
    r'(?:https?://nwvault\.ign\.com)?'
    r'/View\.php\?view=([A-Za-z0-9]+)\.Detail&(?:amp;)?id=(\d+)',
    re.IGNORECASE,
)

# Pattern for other internal vault links (non-detail)
_OTHER_INTERNAL = re.compile(
    r'(href=["\']?)'
    r'(?:https?://nwvault\.ign\.com)'
    r'(/[^\s"\']*)',
    re.IGNORECASE,
)


def fix_html_file(html_path: Path) -> int:
    """Fix broken asset URLs in a single HTML file.

    Rewrites dead vnmedia/vaultnap URLs to local /vault/assets/ paths,
    and View.php detail links to our archive routes.

    Returns:
        Number of URLs rewritten.
    """
    try:
        content = html_path.read_text(
            encoding="utf-8", errors="replace",
        )
    except Exception as e:
        logger.warning(f"Cannot read {html_path}: {e}")
        return 0

    count = 0
    original = content

    # Clean up previous broken #legacy rewrites
    content = content.replace("#legacy/View.php", "/View.php")
    content = content.replace("#legacy/fms/", "/fms/")
    content = content.replace(
        "#legacy/static.php", "/static.php",
    )

    # Fix comment pagination links: /vault/.../5208/&comment_page=2
    # should be /vault/.../5208/?comment_page=2
    content = content.replace("/&comment_page=", "/?comment_page=")

    # Rewrite Ratings.Viewer links to Wayback (new tab)
    # Handles both javascript:popup(...) and already-rewritten URLs
    content = re.sub(
        r'href="(?:javascript:popup\(\')?'
        r'(?:https://web\.archive\.org/web/2012im_/http://nwvault\.ign\.com/)?'
        r'View\.php\?view=Ratings\.Viewer'
        r'&(?:amp;)?cluster=(\d+)&(?:amp;)?id=(\d+)'
        r"""[^"]*\"""",
        lambda m: (
            f'href="{WAYBACK_PREFIX}/http://nwvault.ign.com'
            f"/View.php?view=Ratings.Viewer"
            f'&cluster={m.group(1)}&id={m.group(2)}"'
            f' target="_blank"'
        ),
        content,
    )

    # Revert any previously-set local asset paths back to
    # original URLs so we can re-evaluate each one
    content = re.sub(
        r'(?:/vault/assets/|/_assets/)([\w./\-]+)',
        lambda m: f"http://{m.group(1)}",
        content,
    )

    # Rewrite dead asset URLs — use local if file exists,
    # otherwise use Wayback Machine
    def replace_asset(match: re.Match) -> str:
        nonlocal count
        attr = match.group(1)
        url = match.group(2)
        count += 1
        path = url.split("://", 1)[-1]
        local_file = Path("archive/assets") / path
        if local_file.exists() and local_file.stat().st_size > 100:
            return f"{attr}{LOCAL_ASSET_PREFIX}/{path}"
        return f"{attr}{WAYBACK_PREFIX}/{url}"

    content = ASSET_PATTERN.sub(replace_asset, content)

    # Rewrite Wayback asset URLs to local if file exists
    def replace_wayback_asset(match: re.Match) -> str:
        nonlocal count
        attr = match.group(1)
        path = match.group(2)
        local_file = Path("archive/assets") / path
        if local_file.exists() and local_file.stat().st_size > 100:
            count += 1
            return f"{attr}{LOCAL_ASSET_PREFIX}/{path}"
        # Keep Wayback URL
        return match.group(0)

    content = WAYBACK_ASSET_PATTERN.sub(
        replace_wayback_asset, content,
    )

    # Rewrite thumbnail images to local fullres files
    def replace_thumb(match: re.Match) -> str:
        nonlocal count
        attr = match.group(1)
        fms_cat = match.group(2)
        entry_id = match.group(3)
        timestamp = match.group(4)

        archive_path = _FMS_TO_ARCHIVE.get(fms_cat)
        if archive_path:
            local = (
                Path("archive")
                / archive_path
                / entry_id
                / f"{timestamp}_fullres.jpg"
            )
            if local.exists():
                count += 1
                return (
                    f"{attr}/vault/{archive_path}"
                    f"/{entry_id}/{timestamp}_fullres.jpg"
                )
        # Fallback to Wayback
        return match.group(0)

    content = THUMB_PATTERN.sub(replace_thumb, content)

    # Rewrite fms/Image.php links to open the fullres image directly
    # Pattern: <a href="fms/Image.php?id=XXXXX"><img src="/vault/.../fullres.jpg">
    content = re.sub(
        r'href="(?:fms/Image\.php\?id=\d+)">'
        r'(<img[^>]*src="([^"]+_fullres\.jpg)")',
        lambda m: f'href="{m.group(2)}">{m.group(1)}',
        content,
    )

    # Rewrite View.php detail links to our archive routes
    def replace_detail(match: re.Match) -> str:
        nonlocal count
        attr = match.group(1)
        view_name = match.group(2)
        entry_id = match.group(3)

        key = f"{view_name}.detail".lower()
        path = _VIEW_TO_PATH.get(key)
        if path:
            count += 1
            return f"{attr}/vault/{path}/{entry_id}/"
        # Unknown view — leave as wayback link
        count += 1
        original_url = (
            f"http://nwvault.ign.com/View.php"
            f"?view={view_name}.Detail&id={entry_id}"
        )
        return (
            f"{attr}{WAYBACK_PREFIX}/{original_url}"
        )

    content = _DETAIL_LINK.sub(replace_detail, content)

    # Rewrite other nwvault.ign.com links to Wayback
    def replace_other_internal(match: re.Match) -> str:
        nonlocal count
        attr = match.group(1)
        path = match.group(2)
        count += 1
        return (
            f"{attr}{WAYBACK_PREFIX}"
            f"/http://nwvault.ign.com{path}"
        )

    content = _OTHER_INTERNAL.sub(
        replace_other_internal, content,
    )

    if content != original:
        html_path.write_text(content, encoding="utf-8")

    return count


def fix_all_html(archive_dir: Path) -> dict[str, int]:
    """Fix all HTML files in the archive directory.

    Args:
        archive_dir: Root archive directory.

    Returns:
        Stats dict with total_files and total_rewrites.
    """
    stats = {
        "total_files": 0,
        "total_rewrites": 0,
        "files_modified": 0,
    }

    html_files = (
        list(archive_dir.rglob("*.html"))
        + list(archive_dir.rglob("*.htm"))
    )
    logger.info(f"Found {len(html_files)} HTML files to process")

    for html_path in html_files:
        rewrites = fix_html_file(
            html_path,
        )
        stats["total_files"] += 1
        stats["total_rewrites"] += rewrites
        if rewrites > 0:
            stats["files_modified"] += 1

        if stats["total_files"] % 1000 == 0:
            logger.info(
                f"Processed {stats['total_files']}"
                f"/{len(html_files)} HTML files, "
                f"{stats['total_rewrites']} URLs rewritten"
            )

    logger.info(
        f"HTML fix complete: "
        f"{stats['files_modified']} files modified, "
        f"{stats['total_rewrites']} URLs rewritten "
        f"across {stats['total_files']} files"
    )
    return stats
