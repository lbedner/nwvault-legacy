"""Render listing pages matching the original nwvault HTML style.

Extracts the page shell (header, sidebar, footer) from an
archived HTML page and injects dynamic content from the database.
"""

from pathlib import Path

from app.core.log import logger

ARCHIVE_DIR = Path("archive")

# Shell sources — one per game so the right sidebar matches
_SHELL_SOURCES = {
    "nwn1": ARCHIVE_DIR / "nwn1" / "modules" / "6301" / "index.html",
    "nwn2": ARCHIVE_DIR / "nwn2" / "nwn2modulesenglish" / "529" / "index.html",
}

# Cache: game -> (header, footer)
_shell_cache: dict[str, tuple[str, str]] = {}


def _extract_shell(source: Path) -> tuple[str, str]:
    """Extract header and footer from an archived page."""
    if not source.exists():
        logger.warning(f"Shell source not found: {source}")
        return "<html><body>", "</body></html>"

    content = source.read_text(
        encoding="utf-8", errors="replace",
    )

    # Header: everything up to the skinmenu div line
    marker = '<DIV class="skinmenu">'
    idx = content.find(marker)
    if idx == -1:
        return "<html><body>", "</body></html>"

    end_of_line = content.find("\n", idx)
    header = content[: end_of_line + 1]

    # Footer: from the right sidebar TD to end of page
    footer_marker = "</DIV></TD><TD ALIGN=CENTER VALIGN=TOP"
    footer_idx = content.find(footer_marker)
    footer = (
        content[footer_idx:]
        if footer_idx != -1
        else "</body></html>"
    )

    # Make title replaceable
    # Remove any specific title text between <title> tags
    import re

    header = re.sub(
        r"<title>[^<]*</title>",
        "<title>{{TITLE}}</title>",
        header,
        flags=re.IGNORECASE,
    )

    return header, footer


def _load_shell(
    game: str = "nwn1",
) -> tuple[str, str]:
    """Load and cache the page shell for a game."""
    if game in _shell_cache:
        return _shell_cache[game]

    source = _SHELL_SOURCES.get(
        game,
        _SHELL_SOURCES["nwn1"],
    )
    header, footer = _extract_shell(source)
    _shell_cache[game] = (header, footer)
    return header, footer


def render_page(
    title: str,
    content_html: str,
    game: str = "nwn1",
) -> str:
    """Render a full page with the vault shell and custom content.

    Args:
        title: Page title.
        content_html: HTML to inject into the content area.
        game: "nwn1" or "nwn2" — determines which sidebar to show.

    Returns:
        Complete HTML page string.
    """
    header, footer = _load_shell(game)
    header = header.replace("{{TITLE}}", title)

    return f"{header}\n{content_html}\n{footer}"


def render_entry_table(
    entries: list[dict],
    category_name: str,
    game: str = "nwn1",
    category_slug: str = "modules",
    page: int = 1,
    total_pages: int = 1,
    total: int = 0,
    base_url: str = "",
) -> str:
    """Render a listing table matching the original vault style.

    Args:
        entries: List of entry dicts from the API.
        category_name: Display name (e.g., "NWN MODULES").
        game: Game identifier.
        category_slug: Category slug for links.
        page: Current page number.
        total_pages: Total number of pages.
        total: Total entries count.
        base_url: Base URL for pagination links.

    Returns:
        HTML string for the content area.
    """
    rows = []
    for i, e in enumerate(entries):
        alt = "fmsalt1" if i % 2 == 0 else "fmsalt2"
        entry_id = e.get("entry_id", e.get("id", 0))
        title = e.get("title", "") or "(untitled)"
        author = e.get("author", "") or ""
        score = e.get("score", 0)
        votes = e.get("votes", 0)

        link = f"/vault/{game}/{category_slug}/{entry_id}/"

        rows.append(
            f'<tr class="{alt}">'
            f'<td class="{alt}" width="50%">'
            f'<a href="{link}">{title}</a></td>'
            f'<td class="{alt}" width="30%">{author}</td>'
            f'<td class="{alt}" align="center">'
            f"{score:.2f}</td>"
            f'<td class="{alt}" align="center">'
            f"{votes}</td>"
            f"</tr>"
        )

    table_rows = "\n".join(rows)

    # Pagination
    page_links = []
    for p in range(1, min(total_pages + 1, 20)):
        if p == page:
            page_links.append(f"<b>{p}</b>")
        else:
            page_links.append(
                f'<a href="{base_url}&page={p}">{p}</a>'
            )
    if total_pages > 20:
        page_links.append("...")
        page_links.append(
            f'<a href="{base_url}&page={total_pages}">'
            f"{total_pages}</a>"
        )

    pagination = " | ".join(page_links)

    return f"""
<br>
<center><h1>{category_name}</h1></center>
<center><span style="font-size:8pt">
{total} entries | Page {page} of {total_pages}
</span></center>
<br>
<center>{pagination}</center>
<br>
<table cellspacing="1" cellpadding="6" border="0"
       width="100%" class="fmstborder">
<tr>
  <th class="fmstheader" width="50%">Title</th>
  <th class="fmstheader" width="30%">Author</th>
  <th class="fmstheader" width="10%">Score</th>
  <th class="fmstheader" width="10%">Votes</th>
</tr>
{table_rows}
</table>
<br>
<center>{pagination}</center>
<br>
"""


def render_search_results(
    entries: list[dict],
    query: str,
    total: int,
    page: int = 1,
    total_pages: int = 1,
) -> str:
    """Render search results page."""
    rows = []
    for i, e in enumerate(entries):
        alt = "fmsalt1" if i % 2 == 0 else "fmsalt2"
        entry_id = e.get("entry_id", e.get("id", 0))
        game = e.get("game", "nwn1")
        category = e.get("category", "modules")
        title = e.get("title", "")
        author = e.get("author", "")
        score = e.get("score", 0)
        cat_display = category.replace("nwn2", "").title()

        link = f"/vault/{game}/{category}/{entry_id}/"

        rows.append(
            f'<tr class="{alt}">'
            f'<td class="{alt}">'
            f'<a href="{link}">{title}</a></td>'
            f'<td class="{alt}">{author}</td>'
            f'<td class="{alt}">{cat_display}</td>'
            f'<td class="{alt}" align="center">'
            f"{score:.2f}</td>"
            f"</tr>"
        )

    table_rows = "\n".join(rows)

    return f"""
<br>
<center><h1>SEARCH RESULTS</h1></center>
<center><span style="font-size:8pt">
{total} results for "{query}" | Page {page} of {total_pages}
</span></center>
<br>
<table cellspacing="1" cellpadding="6" border="0"
       width="100%" class="fmstborder">
<tr>
  <th class="fmstheader">Title</th>
  <th class="fmstheader">Author</th>
  <th class="fmstheader">Category</th>
  <th class="fmstheader">Score</th>
</tr>
{table_rows}
</table>
<br>
"""


def render_comments(
    comments: list[dict],
    page: int = 1,
    total_pages: int = 1,
    base_url: str = "",
) -> str:
    """Render comments matching the original vault HTML style.

    Args:
        comments: List of comment dicts with submitter, date, content.
        page: Current page number.
        total_pages: Total pages.
        base_url: Base URL for pagination (e.g., /vault/nwn1/modules/5208/).

    Returns:
        HTML string with comments and pagination.
    """
    blocks = []
    for c in comments:
        submitter = c.get("submitter", "Anonymous")
        date = c.get("date", "")
        content = c.get("content", "")
        # Convert newlines to <br> for display
        content = content.replace("\n", "<br />\n")

        blocks.append(
            f'<table cellspacing=1 cellpadding=10 border=0'
            f' width=100% class="fmstborder">'
            f'<tr class="fmsalt1"><td>'
            f'<span class=""><i>Posted by '
            f"<b>{submitter}</b>"
            f" at {date}</i></span>"
            f"</td></tr>"
            f'<tr class="fmsalt2"><td>'
            f'<span class="comment_body">'
            f"{content}"
            f"</span></td></tr></table><br>\n"
        )

    comment_html = "".join(blocks)

    # Pagination
    page_links = []
    for p in range(1, total_pages + 1):
        if p == page:
            page_links.append(f"<b>{p}</b>")
        else:
            page_links.append(
                f'<a href="{base_url}?comment_page={p}'
                f'#commentmarker">{p}</a>'
            )
    pagination = " | ".join(page_links)

    return (
        f'<a name="commentmarker"></a>\n'
        f"<center>{pagination}</center><br>\n"
        f"{comment_html}"
        f"<center>{pagination}</center><br>\n"
    )
