"""View.php controller — routes legacy vault URLs to the right content.

Handles the same URL patterns the original PHP controller did:
  /View.php?view=Modules.Detail&id=123
  /View.php?view=Modules.List
  /View.php?view=Modules.HOF
  /View.php?view=LatestAdditions&clusters=modules
  /View.php?view=GlobalSearch&q=dragon
"""

from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, func, select

from app.core.db import engine
from app.models.vault import VaultEntry
from app.services.vault.renderer import (
    render_entry_table,
    render_page,
    render_search_results,
)

router = APIRouter()

WAYBACK = "https://web.archive.org/web/2012"
FMS_DIR = Path("archive/fms")

# Map view names to our archive paths (case-insensitive)
_VIEW_TO_GAME_CAT: dict[str, tuple[str, str]] = {
    # NWN1
    "modules": ("nwn1", "modules"),
    "hakpaks": ("nwn1", "hakpaks"),
    "scripts": ("nwn1", "scripts"),
    "portraits": ("nwn1", "portraits"),
    "creatures": ("nwn1", "creatures"),
    "models": ("nwn1", "models"),
    "prefabs": ("nwn1", "prefabs"),
    "other": ("nwn1", "other"),
    "movies": ("nwn1", "movies"),
    "sounds": ("nwn1", "sounds"),
    "textures": ("nwn1", "textures"),
    "characters": ("nwn1", "characters"),
    "gameworld": ("nwn1", "gameworld"),
    # NWN2
    "nwn2modulesenglish": ("nwn2", "nwn2modulesenglish"),
    "nwn2modulesinternational": (
        "nwn2",
        "nwn2modulesinternational",
    ),
    "nwn2hakpaksoriginal": ("nwn2", "nwn2hakpaksoriginal"),
    "nwn2hakpakscombined": ("nwn2", "nwn2hakpakscombined"),
    "nwn2hakpaksmodulespecific": (
        "nwn2",
        "nwn2hakpaksmodulespecific",
    ),
    "nwn2characters": ("nwn2", "nwn2characters"),
    "nwn2scripts": ("nwn2", "nwn2scripts"),
    "nwn2models": ("nwn2", "nwn2models"),
    "nwn2movies": ("nwn2", "nwn2movies"),
    "nwn2other": ("nwn2", "nwn2other"),
    "nwn2plugins": ("nwn2", "nwn2plugins"),
    "nwn2portraits": ("nwn2", "nwn2portraits"),
    "nwn2prefabareas": ("nwn2", "nwn2prefabareas"),
    "nwn2prefabplaceables": ("nwn2", "nwn2prefabplaceables"),
    "nwn2tools": ("nwn2", "nwn2tools"),
    "nwn2tutorials": ("nwn2", "nwn2tutorials"),
    "nwn2ui": ("nwn2", "nwn2ui"),
    "nwn2visualeffects": ("nwn2", "nwn2visualeffects"),
    "nwn2gameworlds": ("nwn2", "nwn2gameworlds"),
    "nwn2strategies": ("nwn2", "nwn2strategies"),
    "nwn2ideas": ("nwn2", "nwn2ideas"),
    "nwn2links": ("nwn2", "nwn2links"),
    "nwn2pwc": ("nwn2", "nwn2pwc"),
}

_DISPLAY_NAMES: dict[str, str] = {
    "modules": "NWN Modules",
    "hakpaks": "NWN Hakpaks",
    "scripts": "NWN Scripts",
    "portraits": "NWN Portraits",
    "creatures": "NWN Creatures",
    "models": "NWN Models",
    "prefabs": "NWN Prefabs",
    "other": "NWN Other",
    "movies": "NWN Movies",
    "sounds": "NWN Sounds",
    "textures": "NWN Textures",
    "characters": "NWN Characters",
    "gameworld": "NWN Gameworlds",
    "nwn2modulesenglish": "NWN2 Modules (English)",
    "nwn2modulesinternational": "NWN2 Modules (Intl)",
    "nwn2hakpaksoriginal": "NWN2 Hakpaks (Original)",
    "nwn2hakpakscombined": "NWN2 Hakpaks (Combined)",
    "nwn2scripts": "NWN2 Scripts",
    "nwn2models": "NWN2 Models",
    "nwn2tools": "NWN2 Tools",
    "nwn2tutorials": "NWN2 Tutorials",
    "nwn2other": "NWN2 Other",
    "nwn2plugins": "NWN2 Plug-ins",
    "nwn2portraits": "NWN2 Portraits",
    "nwn2prefabareas": "NWN2 Prefab Areas",
    "nwn2prefabplaceables": "NWN2 Prefab Placeables",
    "nwn2ui": "NWN2 UI",
    "nwn2visualeffects": "NWN2 Visual Effects",
    "nwn2movies": "NWN2 Movies",
    "nwn2characters": "NWN2 Characters",
    "nwn2gameworlds": "NWN2 Gameworlds",
}


def _resolve_view(view_name: str) -> tuple[str, str] | None:
    """Resolve a View.php view name to (game, category)."""
    base = view_name.split(".")[0].lower()
    return _VIEW_TO_GAME_CAT.get(base)


def _query_entries(
    game: str,
    category: str,
    sort: str = "score",
    order: str = "desc",
    page: int = 1,
    per_page: int = 50,
    min_votes: int = 0,
) -> tuple[list[dict], int]:
    """Query entries from the database."""
    with Session(engine) as session:
        stmt = select(VaultEntry).where(
            VaultEntry.game == game,
            VaultEntry.category == category,
        )
        if min_votes > 0:
            stmt = stmt.where(VaultEntry.votes >= min_votes)

        sort_col = {
            "score": VaultEntry.score,
            "votes": VaultEntry.votes,
            "title": VaultEntry.title,
            "updated": VaultEntry.updated,
            "submitted": VaultEntry.submitted,
            "entry_id": VaultEntry.entry_id,
        }.get(sort, VaultEntry.score)

        if order == "asc":
            stmt = stmt.order_by(sort_col.asc())
        else:
            stmt = stmt.order_by(sort_col.desc())

        count_stmt = (
            select(func.count())
            .select_from(VaultEntry)
            .where(
                VaultEntry.game == game,
                VaultEntry.category == category,
            )
        )
        if min_votes > 0:
            count_stmt = count_stmt.where(
                VaultEntry.votes >= min_votes,
            )
        total = session.exec(count_stmt).one()

        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        entries = session.exec(stmt).all()

        return [
            {
                "entry_id": e.entry_id,
                "title": e.title,
                "author": e.author,
                "score": e.score,
                "votes": e.votes,
                "game": e.game,
                "category": e.category,
            }
            for e in entries
        ], total


@router.get("/static.php", response_model=None)
async def static_php(
    page: str = Query("", description="Static page name"),
) -> HTMLResponse | RedirectResponse:
    """Serve archived static pages (Hall of Fame, etc.)."""
    safe = page.replace("/", "").replace("..", "").replace("\\", "")
    archived = FMS_DIR / f"static_{safe}.html"
    if archived.exists():
        return HTMLResponse(
            content=archived.read_text(
                encoding="utf-8", errors="replace",
            ),
        )
    # Fallback: redirect to Wayback
    return RedirectResponse(
        url=f"{WAYBACK}/http://nwvault.ign.com"
        f"/static.php?page={page}",
        status_code=302,
    )


@router.get("/View.php", response_model=None)
async def view_php(
    view: str = Query("", description="View name"),
    id: int | None = Query(None, description="Entry ID"),
    clusters: str | None = Query(
        None, description="Category for LatestAdditions",
    ),
    q: str | None = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    sort: str = Query("score"),
    dir: str = Query("DESC"),
    show_days_back: int | None = Query(None),
) -> HTMLResponse | RedirectResponse:
    """Handle View.php requests."""
    view_lower = view.lower()

    # --- Detail views: redirect to archived page ---
    if ".detail" in view_lower and id is not None:
        resolved = _resolve_view(view)
        if resolved:
            game, category = resolved
            return RedirectResponse(
                url=f"/vault/{game}/{category}/{id}/",
                status_code=302,
            )
        return RedirectResponse(
            url=f"{WAYBACK}/http://nwvault.ign.com"
            f"/View.php?view={view}&id={id}",
            status_code=302,
        )

    # --- List views: render from database ---
    if ".list" in view_lower:
        resolved = _resolve_view(view)
        if resolved:
            game, category = resolved
            cat_name = _DISPLAY_NAMES.get(
                category, category.upper(),
            )
            per_page = 50
            order = "asc" if dir.upper() == "ASC" else "desc"
            entries, total = _query_entries(
                game, category,
                sort=sort, order=order,
                page=page, per_page=per_page,
            )
            total_pages = (total + per_page - 1) // per_page
            base_url = (
                f"/View.php?view={view}"
                f"&sort={sort}&dir={dir}"
            )

            content = render_entry_table(
                entries, cat_name,
                game=game, category_slug=category,
                page=page, total_pages=total_pages,
                total=total, base_url=base_url,
            )
            return HTMLResponse(
                render_page(
                    f"{cat_name} — Neverwinter Vault",
                    content,
                    game=game,
                )
            )

    # --- Hall of Fame ---
    if ".hof" in view_lower:
        # Serve archived HTML if available
        base = view.split(".")[0]
        hof_path = FMS_DIR / f"HOF_{base}.html"
        if hof_path.exists():
            return HTMLResponse(
                content=hof_path.read_text(
                    encoding="utf-8", errors="replace",
                ),
            )

        # Fallback: render from database
        resolved = _resolve_view(view)
        if resolved:
            game, category = resolved
            cat_name = _DISPLAY_NAMES.get(
                category, category.upper(),
            )
            hof_title = f"HALL OF FAME — {cat_name}"
            entries, total = _query_entries(
                game, category,
                sort="score", order="desc",
                page=page, per_page=50,
                min_votes=5,
            )
            total_pages = (total + 50 - 1) // 50
            base_url = f"/View.php?view={view}"

            content = render_entry_table(
                entries, hof_title,
                game=game, category_slug=category,
                page=page, total_pages=total_pages,
                total=total, base_url=base_url,
            )
            return HTMLResponse(
                render_page(
                    f"{hof_title} — Neverwinter Vault",
                    content,
                    game=game,
                )
            )

    # --- LatestAdditions ---
    if view_lower == "latestadditions" and clusters:
        resolved = _VIEW_TO_GAME_CAT.get(clusters.lower())
        if resolved:
            game, category = resolved
            cat_name = _DISPLAY_NAMES.get(
                category, category.upper(),
            )
            lat_title = f"LATEST {cat_name}"
            entries, total = _query_entries(
                game, category,
                sort="updated", order="desc",
                page=page, per_page=50,
            )
            total_pages = (total + 50 - 1) // 50
            base_url = (
                f"/View.php?view=LatestAdditions"
                f"&clusters={clusters}"
            )

            content = render_entry_table(
                entries, lat_title,
                game=game, category_slug=category,
                page=page, total_pages=total_pages,
                total=total, base_url=base_url,
            )
            return HTMLResponse(
                render_page(
                    f"{lat_title} — Neverwinter Vault",
                    content,
                    game=game,
                )
            )

    # --- RecentUpdates ---
    if view_lower.startswith("recentupdates"):
        game_filter = None
        if "nwn2" in view_lower:
            game_filter = "nwn2"
        elif "allsections" in view_lower:
            game_filter = "nwn1"

        with Session(engine) as session:
            stmt = select(VaultEntry)
            if game_filter:
                stmt = stmt.where(
                    VaultEntry.game == game_filter,
                )
            stmt = stmt.order_by(
                VaultEntry.updated.desc(),
            ).limit(100)
            entries = session.exec(stmt).all()

            entry_list = [
                {
                    "entry_id": e.entry_id,
                    "title": e.title,
                    "author": e.author,
                    "score": e.score,
                    "votes": e.votes,
                    "game": e.game,
                    "category": e.category,
                }
                for e in entries
            ]

        title = "RECENT UPDATES"
        if game_filter:
            title += f" — {game_filter.upper()}"

        rows = []
        for i, e in enumerate(entry_list):
            alt = "fmsalt1" if i % 2 == 0 else "fmsalt2"
            link = (
                f"/vault/{e['game']}/{e['category']}"
                f"/{e['entry_id']}/"
            )
            cat = e["category"].replace("nwn2", "").title()
            rows.append(
                f'<tr class="{alt}">'
                f'<td class="{alt}" width="50%">'
                f'<a href="{link}">{e["title"]}</a></td>'
                f'<td class="{alt}" width="25%">'
                f'{e["author"]}</td>'
                f'<td class="{alt}" width="15%">'
                f'{cat}</td>'
                f'<td class="{alt}" width="10%"'
                f' align="center">'
                f'{e["score"]:.2f}</td>'
                f"</tr>"
            )

        content = f"""
<br><center><h1>{title}</h1></center><br>
<table cellspacing="1" cellpadding="6" border="0"
       width="100%" class="fmstborder">
<tr>
  <th class="fmstheader" width="50%">Title</th>
  <th class="fmstheader" width="25%">Author</th>
  <th class="fmstheader" width="15%">Category</th>
  <th class="fmstheader" width="10%">Score</th>
</tr>
{"".join(rows)}
</table><br>
"""
        return HTMLResponse(
            render_page(
                f"{title} — Neverwinter Vault",
                content,
                game=game_filter or "nwn1",
            )
        )

    # --- GlobalSearch ---
    if view_lower == "globalsearch" and q:
        with Session(engine) as session:
            stmt = (
                select(VaultEntry)
                .where(
                    (VaultEntry.title.contains(q))
                    | (VaultEntry.description.contains(q))
                )
                .order_by(VaultEntry.score.desc())
            )
            count_stmt = (
                select(func.count())
                .select_from(VaultEntry)
                .where(
                    (VaultEntry.title.contains(q))
                    | (VaultEntry.description.contains(q))
                )
            )
            total = session.exec(count_stmt).one()
            per_page = 50
            stmt = stmt.offset((page - 1) * per_page).limit(
                per_page,
            )
            entries = session.exec(stmt).all()

            entry_list = [
                {
                    "entry_id": e.entry_id,
                    "title": e.title,
                    "author": e.author,
                    "score": e.score,
                    "game": e.game,
                    "category": e.category,
                }
                for e in entries
            ]

        total_pages = (total + per_page - 1) // per_page
        content = render_search_results(
            entry_list, q, total,
            page=page, total_pages=total_pages,
        )
        return HTMLResponse(
            render_page(
                f'Search: "{q}" — Neverwinter Vault',
                content,
            )
        )

    # --- Fallback: redirect to Wayback Machine ---
    params = f"view={view}"
    if id is not None:
        params += f"&id={id}"
    if clusters:
        params += f"&clusters={clusters}"

    return RedirectResponse(
        url=f"{WAYBACK}/http://nwvault.ign.com"
        f"/View.php?{params}",
        status_code=302,
    )


@router.get("/fms/TopRated.php", response_model=None)
async def top_rated_php(
    content: str = Query("modules", description="Category"),
    page: int = Query(1, ge=1),
) -> HTMLResponse:
    """Serve archived Top Rated page, with DB fallback."""
    safe = content.replace("/", "").replace("..", "")
    archived = FMS_DIR / f"TopRated_{safe}.html"
    if archived.exists():
        return HTMLResponse(
            content=archived.read_text(
                encoding="utf-8", errors="replace",
            ),
        )

    # Fallback: render from database
    resolved = _VIEW_TO_GAME_CAT.get(content.lower())
    if not resolved:
        return HTMLResponse(
            render_page(
                "Not Found — Neverwinter Vault",
                "<center><h1>Category not found</h1></center>",
            )
        )

    game, category = resolved
    cat_display = _DISPLAY_NAMES.get(
        content.lower(), content.upper(),
    )

    per_page = 50
    entries, total = _query_entries(
        game, category,
        sort="score", order="desc",
        page=page, per_page=per_page,
        min_votes=3,
    )
    total_pages = (total + per_page - 1) // per_page
    base_url = f"/fms/TopRated.php?content={content}"

    content_html = render_entry_table(
        entries, f"TOP RATED {cat_display}",
        game=game, category_slug=category,
        page=page, total_pages=total_pages,
        total=total, base_url=base_url,
    )
    return HTMLResponse(
        render_page(
            f"Top Rated {cat_display} — Neverwinter Vault",
            content_html,
            game=game,
        )
    )
