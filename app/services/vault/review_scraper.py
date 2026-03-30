"""Scrape user reviews from Wayback Machine Ratings.Viewer pages."""

import re

import httpx
from lxml import etree

from app.core.log import logger

WAYBACK_BASE = "https://web.archive.org/web/2013id_"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# The cluster parameter varies by category — 9 is modules
# We try without it first since Wayback might have it cached
_CLUSTER_MAP = {
    "modules": 9,
    "hakpaks": 2,
    "scripts": 7,
    "portraits": 6,
    "creatures": 8,
    "models": 3,
    "prefabs": 10,
    "other": 5,
    "movies": 11,
    "sounds": 12,
    "textures": 13,
    "characters": 1,
    "gameworld": 4,
}


def parse_ratings_html(html: str) -> list[dict]:
    """Parse a Ratings.Viewer HTML page into review dicts.

    The page has a table with rows alternating fmsalt1/fmsalt2:
    - Column 1: Username (with link containing user ID)
    - Column 2: Score (float)
    - Column 3: Review text
    - Column 4: Date (MM-DD-YYYY)
    """
    reviews = []

    # Use lxml with HTML parser for tolerance
    parser = etree.HTMLParser()
    tree = etree.fromstring(html.encode("utf-8", errors="replace"), parser)
    if tree is None:
        return []

    # Find all table rows with fmsalt1 or fmsalt2 class
    rows = tree.xpath(
        '//tr[@class="fmsalt1"] | //tr[@class="fmsalt2"]'
    )

    for row in rows:
        tds = row.findall("td")
        if len(tds) < 4:
            continue

        # Username and user ID
        username = ""
        user_id = None
        link = tds[0].find(".//a")
        if link is not None:
            username = (link.text or "").strip()
            href = link.get("href", "")
            id_match = re.search(r"id=(\d+)", href)
            if id_match:
                user_id = int(id_match.group(1))

        # Score
        score_text = (tds[1].text or "").strip()
        try:
            score = float(score_text)
        except (ValueError, TypeError):
            continue

        # Review content — may contain <br/> tags
        content_parts = []
        for el in tds[2].iter():
            if el.text:
                content_parts.append(el.text)
            if el.tail:
                content_parts.append(el.tail)
        content = " ".join(content_parts).strip()

        # Date
        date = (tds[3].text or "").strip()

        if username or content:
            reviews.append({
                "username": username,
                "user_vault_id": user_id,
                "score": score,
                "content": content,
                "date": date,
            })

    return reviews


async def scrape_reviews_for_entry(
    client: httpx.AsyncClient,
    entry_id: int,
    category: str = "modules",
    delay: float = 3.0,
) -> list[dict]:
    """Scrape reviews for a single entry from Wayback Machine.

    Args:
        client: HTTP client.
        entry_id: The vault entry ID.
        category: Category slug for cluster mapping.
        delay: Seconds to wait before request (rate limiting).

    Returns:
        List of review dicts.
    """
    cluster = _CLUSTER_MAP.get(category, 9)

    # Rate limit
    if delay > 0:
        import asyncio
        await asyncio.sleep(delay)

    url = (
        f"{WAYBACK_BASE}/http://nwvault.ign.com"
        f"/View.php?view=Ratings.Viewer"
        f"&cluster={cluster}&id={entry_id}"
    )

    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return []

        html = resp.text
        # Check it's actually a ratings page, not a 404/error
        if "fmsalt1" not in html and "fmsalt2" not in html:
            return []

        return parse_ratings_html(html)

    except Exception as e:
        logger.warning(
            f"Failed to scrape reviews for entry {entry_id}: {e}"
        )
        raise  # Let arq mark it as failed and retry


async def scrape_and_store_reviews(
    entry_db_id: int,
    entry_id: int,
    category: str = "modules",
    delay: float = 1.5,
) -> int:
    """Scrape reviews for an entry and store them in the DB.

    Args:
        entry_db_id: Our database primary key for the entry.
        entry_id: The original vault entry ID.
        category: Category slug.
        delay: Rate limit delay.

    Returns:
        Number of reviews stored.
    """
    from sqlmodel import Session, select

    from app.core.db import engine
    from app.models.vault import VaultReview

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
    ) as client:
        reviews = await scrape_reviews_for_entry(
            client, entry_id, category, delay,
        )

    if not reviews:
        return 0

    with Session(engine) as session:
        # Check for existing reviews to avoid duplicates
        existing = session.exec(
            select(VaultReview).where(
                VaultReview.entry_id == entry_db_id,
            )
        ).all()
        existing_users = {
            (r.username, r.date) for r in existing
        }

        stored = 0
        for r in reviews:
            key = (r["username"], r["date"])
            if key in existing_users:
                continue

            session.add(VaultReview(
                entry_id=entry_db_id,
                username=r["username"],
                user_vault_id=r.get("user_vault_id"),
                score=r["score"],
                content=r["content"],
                date=r["date"],
            ))
            stored += 1

        session.commit()

    return stored
