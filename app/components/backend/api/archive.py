"""Serve original archived HTML pages and assets from the local archive."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from sqlmodel import Session, select

from app.core.db import engine
from app.models.vault import VaultComment, VaultEntry

router = APIRouter()

ARCHIVE_DIR = Path("archive")

ALLOWED_EXTENSIONS = {
    ".html", ".htm", ".xml", ".jpg", ".jpeg", ".png", ".gif",
    ".bmp", ".css", ".js", ".txt", ".ico",
}

MIME_TYPES = {
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "application/xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".css": "text/css",
    ".js": "application/javascript",
    ".txt": "text/plain",
    ".ico": "image/x-icon",
}

COMMENTS_PER_PAGE = 10


def _render_comments_html(
    comments: list, page: int, total: int, base_url: str,
) -> str:
    """Render a comments section matching the vault style."""
    total_pages = (total + COMMENTS_PER_PAGE - 1) // COMMENTS_PER_PAGE

    # Pagination
    pages = []
    for p in range(1, min(total_pages + 1, 12)):
        if p == page:
            pages.append(f"<b>{p}</b>")
        else:
            pages.append(
                f'<a href="{base_url}?comment_page={p}">{p}</a>'
            )
    if total_pages > 11:
        pages.append("..")
        pages.append(
            f'<a href="{base_url}?comment_page={total_pages}">'
            f"{total_pages}</a>"
        )
    pagination = " ".join(pages)

    rows = []
    for c in comments:
        rows.append(
            f'<table cellspacing=1 cellpadding=10 border=0 '
            f'width=100% class="fmstborder">'
            f'<tr class="fmsalt1"><td>'
            f'<span class=""><i>Posted by '
            f"<b>{c.submitter}</b> at {c.date}</i></span>"
            f"</td></tr>"
            f'<tr class="fmsalt2"><td>'
            f'<span class="comment_body">'
            f"{c.content}</span></td></tr></table><br>\n"
        )

    return (
        f'<center><b>Comments ({total}):</b><br><br>'
        f"{pagination}</center><br>\n"
        f"{''.join(rows)}"
        f"<center>{pagination}</center><br>\n"
    )


@router.get("/{game}/{category}/{entry_id}/")
def serve_entry_page(
    game: str,
    category: str,
    entry_id: int,
    comment_page: int = Query(1, ge=1),
) -> HTMLResponse:
    """Serve the archived HTML page, with DB-backed comment pagination."""
    html_path = (
        ARCHIVE_DIR / game / category / str(entry_id) / "index.html"
    )

    if not html_path.exists():
        raise HTTPException(
            status_code=404, detail="Archived page not found",
        )

    try:
        html_path.resolve().relative_to(ARCHIVE_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    content = html_path.read_text(encoding="utf-8", errors="replace")

    # If requesting a comment page beyond 1, swap the comments
    if comment_page > 1:
        with Session(engine) as session:
            # Find the entry in DB
            entry = session.exec(
                select(VaultEntry).where(
                    VaultEntry.game == game,
                    VaultEntry.category == category,
                    VaultEntry.entry_id == entry_id,
                )
            ).first()

            if entry:
                from sqlmodel import func

                total_count = session.exec(
                    select(func.count())
                    .select_from(VaultComment)
                    .where(
                        VaultComment.entry_id == entry.id,
                    )
                ).one()

                offset = (comment_page - 1) * COMMENTS_PER_PAGE
                comments = session.exec(
                    select(VaultComment)
                    .where(
                        VaultComment.entry_id == entry.id,
                    )
                    .offset(offset)
                    .limit(COMMENTS_PER_PAGE)
                ).all()

                base_url = f"/vault/{game}/{category}/{entry_id}/"
                comments_html = _render_comments_html(
                    comments, comment_page,
                    total_count, base_url,
                )

                # Replace the existing comments section
                # Find the comments header
                import re
                marker_match = re.search(
                    r'<font[^>]*><b>Comments \(\d+\)',
                    content,
                )
                marker_idx = (
                    marker_match.start() if marker_match else -1
                )
                if marker_idx == -1:
                    marker_idx = content.find("Comments (")

                if marker_idx != -1:
                    # Find the end of the comments section
                    end_marker = '<a name="NewComment"'
                    end_idx = content.find(
                        end_marker, marker_idx,
                    )
                    if end_idx != -1:
                        content = (
                            content[:marker_idx]
                            + comments_html
                            + content[end_idx:]
                        )

    return HTMLResponse(content=content)


@router.get("/{game}/{category}/{entry_id}/{filename:path}")
def serve_entry_asset(
    game: str,
    category: str,
    entry_id: int,
    filename: str,
) -> FileResponse:
    """Serve an asset file (screenshot, etc.)."""
    # Strip any query-string artifacts from filename
    clean = filename.split("&")[0].split("?")[0]
    file_path = ARCHIVE_DIR / game / category / str(entry_id) / clean

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        file_path.resolve().relative_to(ARCHIVE_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    suffix = file_path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=403, detail="File type not allowed",
        )

    media_type = MIME_TYPES.get(suffix, "application/octet-stream")
    return FileResponse(file_path, media_type=media_type)
