"""Public API endpoints for browsing the NWVault archive."""

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session, func, select

from app.core.db import engine
from app.models.vault import (
    VaultCategory,
    VaultComment,
    VaultEntry,
    VaultFile,
    VaultScreenshot,
)

router = APIRouter()


@router.get("/categories")
def list_categories(
    game: str | None = Query(None, description="Filter by game: nwn1, nwn2"),
) -> list[dict]:
    """List all vault categories with entry counts."""
    with Session(engine) as session:
        stmt = select(VaultCategory)
        if game:
            stmt = stmt.where(VaultCategory.game == game)
        stmt = stmt.order_by(VaultCategory.game, VaultCategory.display_name)
        categories = session.exec(stmt).all()
        return [
            {
                "id": c.id,
                "slug": c.slug,
                "game": c.game,
                "display_name": c.display_name,
                "entry_count": c.entry_count,
            }
            for c in categories
        ]


@router.get("/entries")
def list_entries(
    game: str | None = Query(None, description="Filter by game: nwn1, nwn2"),
    category: str | None = Query(None, description="Filter by category slug"),
    sort: str = Query(
        "score",
        description="Sort by: score, votes, title, updated, entry_id",
    ),
    order: str = Query("desc", description="Sort order: asc, desc"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(25, ge=1, le=100, description="Results per page"),
) -> dict:
    """List vault entries with filtering, sorting, and pagination."""
    with Session(engine) as session:
        stmt = select(VaultEntry)

        if game:
            stmt = stmt.where(VaultEntry.game == game)
        if category:
            stmt = stmt.where(VaultEntry.category == category)

        # Sorting
        sort_column = {
            "score": VaultEntry.score,
            "votes": VaultEntry.votes,
            "title": VaultEntry.title,
            "updated": VaultEntry.updated,
            "entry_id": VaultEntry.entry_id,
            "author": VaultEntry.author,
        }.get(sort, VaultEntry.score)

        if order == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        # Count total
        count_stmt = select(func.count()).select_from(VaultEntry)
        if game:
            count_stmt = count_stmt.where(VaultEntry.game == game)
        if category:
            count_stmt = count_stmt.where(VaultEntry.category == category)
        total = session.exec(count_stmt).one()

        # Paginate
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        entries = session.exec(stmt).all()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
            "entries": [
                {
                    "id": e.id,
                    "entry_id": e.entry_id,
                    "game": e.game,
                    "category": e.category,
                    "title": e.title,
                    "author": e.author,
                    "score": e.score,
                    "votes": e.votes,
                    "total_comments": e.total_comments,
                    "submitted": e.submitted,
                    "updated": e.updated,
                    "has_html": e.has_html,
                }
                for e in entries
            ],
        }


@router.get("/entries/{entry_db_id}")
def get_entry(entry_db_id: int) -> dict:
    """Get a single vault entry with all its related data."""
    with Session(engine) as session:
        entry = session.get(VaultEntry, entry_db_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        comments = session.exec(
            select(VaultComment)
            .where(VaultComment.entry_id == entry.id)
        ).all()

        files = session.exec(
            select(VaultFile)
            .where(VaultFile.entry_id == entry.id)
        ).all()

        screenshots = session.exec(
            select(VaultScreenshot)
            .where(VaultScreenshot.entry_id == entry.id)
        ).all()

        return {
            "id": entry.id,
            "entry_id": entry.entry_id,
            "game": entry.game,
            "category": entry.category,
            "title": entry.title,
            "author": entry.author,
            "description": entry.description,
            "submitted": entry.submitted,
            "updated": entry.updated,
            "score": entry.score,
            "votes": entry.votes,
            "total_comments": entry.total_comments,
            "extra_fields": entry.extra_fields,
            "has_html": entry.has_html,
            "html_path": entry.html_path,
            "comments": [
                {"submitter": c.submitter, "date": c.date, "content": c.content}
                for c in comments
            ],
            "files": [
                {
                    "filepath": f.filepath,
                    "filename": f.filename,
                    "title": f.title,
                    "description": f.description,
                    "file_type": f.file_type,
                }
                for f in files
            ],
            "screenshots": [
                {
                    "filepath": s.filepath,
                    "filename": s.filename,
                    "thumb_src": s.thumb_src,
                    "local_path": s.local_path,
                }
                for s in screenshots
            ],
        }


@router.get("/search")
def search_entries(
    q: str = Query(..., min_length=2, description="Search query"),
    game: str | None = Query(None, description="Filter by game"),
    category: str | None = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
) -> dict:
    """Full-text search across entry titles and descriptions."""
    with Session(engine) as session:
        stmt = select(VaultEntry).where(
            (VaultEntry.title.contains(q)) | (VaultEntry.description.contains(q))
        )

        if game:
            stmt = stmt.where(VaultEntry.game == game)
        if category:
            stmt = stmt.where(VaultEntry.category == category)

        stmt = stmt.order_by(VaultEntry.score.desc())

        # Count
        count_stmt = select(func.count()).select_from(VaultEntry).where(
            (VaultEntry.title.contains(q)) | (VaultEntry.description.contains(q))
        )
        if game:
            count_stmt = count_stmt.where(VaultEntry.game == game)
        if category:
            count_stmt = count_stmt.where(VaultEntry.category == category)
        total = session.exec(count_stmt).one()

        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        entries = session.exec(stmt).all()

        return {
            "query": q,
            "total": total,
            "page": page,
            "per_page": per_page,
            "entries": [
                {
                    "id": e.id,
                    "entry_id": e.entry_id,
                    "game": e.game,
                    "category": e.category,
                    "title": e.title,
                    "author": e.author,
                    "score": e.score,
                    "votes": e.votes,
                    "has_html": e.has_html,
                }
                for e in entries
            ],
        }


@router.get("/top")
def top_entries(
    game: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> list[dict]:
    """Get top-rated vault entries."""
    with Session(engine) as session:
        stmt = select(VaultEntry).where(VaultEntry.votes > 0)

        if game:
            stmt = stmt.where(VaultEntry.game == game)
        if category:
            stmt = stmt.where(VaultEntry.category == category)

        stmt = stmt.order_by(VaultEntry.score.desc(), VaultEntry.votes.desc())
        stmt = stmt.limit(limit)
        entries = session.exec(stmt).all()

        return [
            {
                "id": e.id,
                "entry_id": e.entry_id,
                "game": e.game,
                "category": e.category,
                "title": e.title,
                "author": e.author,
                "score": e.score,
                "votes": e.votes,
                "has_html": e.has_html,
            }
            for e in entries
        ]


@router.get("/stats")
def vault_stats() -> dict:
    """Get overall vault statistics."""
    with Session(engine) as session:
        total_entries = session.exec(
            select(func.count()).select_from(VaultEntry)
        ).one()
        total_comments = session.exec(
            select(func.count()).select_from(VaultComment)
        ).one()
        total_categories = session.exec(
            select(func.count()).select_from(VaultCategory)
        ).one()
        total_with_html = session.exec(
            select(func.count()).select_from(VaultEntry).where(VaultEntry.has_html.is_(True))
        ).one()

        nwn1_count = session.exec(
            select(func.count())
            .select_from(VaultEntry)
            .where(VaultEntry.game == "nwn1")
        ).one()
        nwn2_count = session.exec(
            select(func.count())
            .select_from(VaultEntry)
            .where(VaultEntry.game == "nwn2")
        ).one()

        return {
            "total_entries": total_entries,
            "total_comments": total_comments,
            "total_categories": total_categories,
            "entries_with_html": total_with_html,
            "nwn1_entries": nwn1_count,
            "nwn2_entries": nwn2_count,
        }
