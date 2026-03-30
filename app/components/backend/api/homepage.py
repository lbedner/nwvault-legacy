"""Serve the archived NWVault homepage at the site root."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HOMEPAGE_PATH = Path("archive/homepage.html")


@router.get("/")
def serve_homepage() -> HTMLResponse:
    """Serve the original NWVault homepage."""
    if not HOMEPAGE_PATH.exists():
        return HTMLResponse(
            content="<h1>Homepage not found</h1>",
            status_code=404,
        )

    content = HOMEPAGE_PATH.read_text(
        encoding="utf-8", errors="replace",
    )
    return HTMLResponse(content=content)
