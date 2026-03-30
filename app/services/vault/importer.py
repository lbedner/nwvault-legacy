"""Parse vault XML data files and import entries into the database."""

from pathlib import Path
import re

from lxml import etree
from sqlmodel import Session, select

from app.core.db import db_session
from app.core.log import logger
from app.models.vault import (
    VaultCategory,
    VaultComment,
    VaultEntry,
    VaultFile,
    VaultScreenshot,
)

# Known fields that go into dedicated columns (rest goes to extra_fields)
KNOWN_FIELDS = {
    "Title", "Name", "Author", "Description", "Submitted", "Updated",
    "Total Comments", "Score", "Votes",
}

# NWN1 categories and their display names
NWN1_CATEGORIES = {
    "artwork": "Artwork",
    "characters": "Characters",
    "community_news": "Community News",
    "creatures": "Creatures",
    "gameworld": "Gameworlds",
    "hakpaks": "Hakpaks",
    "ideas": "Ideas",
    "links": "Community Links",
    "models": "Models",
    "moduleideas": "Module Ideas",
    "modules": "Modules",
    "movies": "Movies",
    "other": "Other",
    "portraits": "Portraits",
    "prefabs": "Prefabs",
    "screenshots": "User Screenshots",
    "scripts": "Scripts",
    "sounds": "Sounds",
    "textures": "Textures",
}

# NWN2 categories and their display names
NWN2_CATEGORIES = {
    "nwn2characters": "Characters",
    "nwn2gameworlds": "Gameworlds",
    "nwn2hakpakscombined": "Hakpaks: Combined",
    "nwn2hakpaksmodulespecific": "Hakpaks: Module-Specific",
    "nwn2hakpaksoriginal": "Hakpaks: Original",
    "nwn2ideas": "Ideas",
    "nwn2links": "Community Links",
    "nwn2models": "Models",
    "nwn2modulesenglish": "Modules (English)",
    "nwn2modulesinternational": "Modules (International)",
    "nwn2movies": "Movies",
    "nwn2other": "Other",
    "nwn2plugins": "Plug-ins",
    "nwn2portraits": "Portraits",
    "nwn2prefabareas": "Prefab Areas",
    "nwn2prefabplaceables": "Prefab Placeables",
    "nwn2pwc": "PWC Files",
    "nwn2scripts": "Scripts",
    "nwn2strategies": "Strategies",
    "nwn2textures": "Textures",
    "nwn2tools": "Tools",
    "nwn2tutorials": "Tutorials",
    "nwn2ui": "UI",
    "nwn2visualeffects": "Visual Effects",
}


def _safe_float(value: str) -> float:
    """Parse a float, returning 0.0 on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(value: str) -> int:
    """Parse an int, returning 0 on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _el_text(el: object) -> str:
    """Safely get text from an lxml element, handling encoding errors."""
    try:
        return el.text or ""  # type: ignore[union-attr]
    except UnicodeDecodeError:
        # lxml hit bad bytes — extract raw and decode with replacement
        try:
            raw = etree.tostring(el, encoding="unicode")  # type: ignore[arg-type]
            # Extract text between > and <
            start = raw.find(">") + 1
            end = raw.rfind("</")
            if start > 0 and end > start:
                return raw[start:end]
        except Exception:
            pass
        return ""


def _el_get(el: object, attr: str, default: str = "") -> str:
    """Safely get an attribute from an lxml element."""
    try:
        return el.get(attr, default) or default  # type: ignore[union-attr]
    except UnicodeDecodeError:
        return default


# HTML entities commonly found in vault XML (not valid in XML)
_HTML_ENTITIES = {
    "&nbsp;": " ",
    "&copy;": "\u00a9",
    "&reg;": "\u00ae",
    "&trade;": "\u2122",
    "&mdash;": "\u2014",
    "&ndash;": "\u2013",
    "&laquo;": "\u00ab",
    "&raquo;": "\u00bb",
    "&hellip;": "\u2026",
    "&bull;": "\u2022",
    "&ldquo;": "\u201c",
    "&rdquo;": "\u201d",
    "&lsquo;": "\u2018",
    "&rsquo;": "\u2019",
    "&times;": "\u00d7",
    "&divide;": "\u00f7",
    "&deg;": "\u00b0",
    "&micro;": "\u00b5",
    "&para;": "\u00b6",
    "&sect;": "\u00a7",
    "&euro;": "\u20ac",
    "&pound;": "\u00a3",
    "&yen;": "\u00a5",
    "&cent;": "\u00a2",
    "&frac12;": "\u00bd",
    "&frac14;": "\u00bc",
    "&frac34;": "\u00be",
    "&iexcl;": "\u00a1",
    "&iquest;": "\u00bf",
    "&acute;": "\u00b4",
    "&cedil;": "\u00b8",
    "&ordf;": "\u00aa",
    "&ordm;": "\u00ba",
    "&sup1;": "\u00b9",
    "&sup2;": "\u00b2",
    "&sup3;": "\u00b3",
}

# Pattern to catch any remaining undefined &word; entities
_ENTITY_PATTERN = re.compile(r"&(\w+);")
_VALID_XML_ENTITIES = {"amp", "lt", "gt", "apos", "quot"}


def _read_and_clean_xml(xml_path: Path) -> str | None:
    """Read an XML file and clean it for parsing.

    The vault XML files declare UTF-8 but are actually Latin-1/
    Windows-1252 encoded, and contain HTML entities like &nbsp;.
    """
    try:
        raw = xml_path.read_bytes()
    except Exception as e:
        logger.error(f"Cannot read {xml_path}: {e}")
        return None

    # Decode as Latin-1 (superset of ASCII, handles all 0x00-0xFF)
    content = raw.decode("latin-1")

    # Fix the encoding declaration to match what we now have
    content = content.replace(
        'encoding="UTF-8"', 'encoding="unicode"', 1
    )
    # Remove XML declaration entirely — ET.fromstring doesn't need it
    content = re.sub(
        r'<\?xml[^?]*\?>\s*', "", content, count=1
    )

    # Replace known HTML entities
    for entity, replacement in _HTML_ENTITIES.items():
        content = content.replace(entity, replacement)

    # Replace any remaining unknown &word; entities
    def _replace_entity(m: re.Match) -> str:
        name = m.group(1)
        if name in _VALID_XML_ENTITIES:
            return m.group(0)  # Keep valid XML entities
        return ""  # Remove unknown entities

    content = _ENTITY_PATTERN.sub(_replace_entity, content)

    # Fix bare & that aren't part of valid entities
    # Match & not followed by amp; lt; gt; apos; quot; or #
    content = re.sub(
        r"&(?!amp;|lt;|gt;|apos;|quot;|#)",
        "&amp;",
        content,
    )

    # Fix bare < that aren't XML tag starts
    # A real XML tag: < followed by / or letter or ! or ?
    # Anything else (digits, spaces, etc.) is content
    content = re.sub(
        r"<(?![/!?a-zA-Z])",
        "&lt;",
        content,
    )

    # Remove control characters (except tab, newline, carriage return)
    content = "".join(
        c for c in content
        if c in "\t\n\r" or (ord(c) >= 0x20)
    )

    return content


def parse_xml_file(xml_path: Path) -> list[dict]:
    """Parse a *_data.xml file and return a list of entry dicts.

    Args:
        xml_path: Path to the XML data file.

    Returns:
        List of dicts, each representing one vault entry.
    """
    entries = []

    content = _read_and_clean_xml(xml_path)
    if content is None:
        return []

    # Use lxml with recover=True to handle malformed XML
    # (user-generated content from 2002-2012 with bare <, &, etc.)
    content_bytes = content.encode("utf-8")
    parser = etree.XMLParser(recover=True, encoding="utf-8")
    try:
        root = etree.fromstring(content_bytes, parser=parser)
    except Exception as e:
        logger.error(f"Failed to parse {xml_path}: {e}")
        return []

    for article in root.iter("article"):
        entry: dict = {
            "entry_id": _safe_int(
                _el_get(article, "entryid", "0")
            ),
            "fields": {},
            "comments": [],
            "files": [],
            "screenshots": [],
        }

        # Parse fields
        for field in article.findall("field"):
            name = _el_get(field, "fieldname")
            value = _el_text(field)
            if name in KNOWN_FIELDS:
                entry["fields"][name] = value
            else:
                if "extra" not in entry:
                    entry["extra"] = {}
                entry["extra"][name] = value

        # Parse comments
        for comment_group in article.findall("comments"):
            for fc in comment_group.findall("field_comment"):
                ce = fc.find("comment_entry")
                if ce is not None:
                    entry["comments"].append({
                        "submitter": _el_get(ce, "submitter"),
                        "date": _el_get(ce, "date"),
                        "content": _el_text(ce),
                    })

        # Parse files
        for files_group in article.findall("files"):
            for ff in files_group.findall("field_file"):
                filepath_el = ff.find("filepath")
                filename_el = ff.find("filename")
                data_el = ff.find("data")

                file_entry: dict = {
                    "filepath": _el_text(filepath_el) if filepath_el is not None else "",
                    "filename": _el_text(filename_el) if filename_el is not None else "",
                }
                if data_el is not None:
                    title_el = data_el.find("title")
                    desc_el = data_el.find("description")
                    type_el = data_el.find("type")
                    file_entry["title"] = (
                        _el_text(title_el) if title_el is not None else ""
                    )
                    file_entry["description"] = (
                        _el_text(desc_el) if desc_el is not None else ""
                    )
                    file_entry["file_type"] = (
                        _el_text(type_el) if type_el is not None else ""
                    )

                entry["files"].append(file_entry)

        # Parse screenshots
        for screens_group in article.findall("screenshots"):
            for sf in screens_group.findall("field_file"):
                filepath_el = sf.find("filepath")
                filename_el = sf.find("filename")
                data_el = sf.find("data")

                screen_entry: dict = {
                    "filepath": _el_text(filepath_el) if filepath_el is not None else "",
                    "filename": _el_text(filename_el) if filename_el is not None else "",
                }
                if data_el is not None:
                    src_el = data_el.find("src")
                    screen_entry["thumb_src"] = (
                        _el_text(src_el)
                        if src_el is not None
                        else ""
                    )

                entry["screenshots"].append(screen_entry)

        entries.append(entry)

    return entries


def import_category(
    session: Session,
    game: str,
    category_slug: str,
    entries: list[dict],
    archive_dir: Path | None = None,
) -> int:
    """Import parsed entries for a single category into the database.

    Args:
        session: Database session.
        game: "nwn1" or "nwn2".
        category_slug: Category identifier (e.g., "modules").
        entries: Parsed entry dicts from parse_xml_file.
        archive_dir: Optional archive directory for checking local HTML files.

    Returns:
        Number of entries imported.
    """
    # Upsert the category
    stmt = select(VaultCategory).where(
        VaultCategory.slug == category_slug,
        VaultCategory.game == game,
    )
    cat = session.exec(stmt).first()
    if not cat:
        all_cats = {**NWN1_CATEGORIES, **NWN2_CATEGORIES}
        cat = VaultCategory(
            slug=category_slug,
            game=game,
            display_name=all_cats.get(
                category_slug,
                category_slug.replace("_", " ").title(),
            ),
            entry_count=0,
        )
        session.add(cat)
        session.flush()

    imported = 0

    for entry_data in entries:
        entry_id = entry_data["entry_id"]
        fields = entry_data.get("fields", {})

        # Check if entry already exists
        existing = session.exec(
            select(VaultEntry).where(
                VaultEntry.entry_id == entry_id,
                VaultEntry.game == game,
                VaultEntry.category == category_slug,
            )
        ).first()
        if existing:
            continue

        # Determine HTML path
        html_path = None
        has_html = False
        if archive_dir:
            html_candidate = (
                archive_dir / game / category_slug
                / str(entry_id) / "index.html"
            )
            if html_candidate.exists():
                html_path = str(html_candidate.relative_to(archive_dir))
                has_html = True

        vault_entry = VaultEntry(
            entry_id=entry_id,
            game=game,
            category=category_slug,
            category_id=cat.id,
            title=fields.get("Title", "") or fields.get("Name", ""),
            author=fields.get("Author", ""),
            description=fields.get("Description", ""),
            submitted=fields.get("Submitted", ""),
            updated=fields.get("Updated", ""),
            score=_safe_float(fields.get("Score", "0")),
            votes=_safe_int(fields.get("Votes", "0")),
            total_comments=_safe_int(fields.get("Total Comments", "0")),
            extra_fields=entry_data.get("extra"),
            html_path=html_path,
            has_html=has_html,
        )
        session.add(vault_entry)
        session.flush()

        # Add comments
        for c in entry_data.get("comments", []):
            if not c.get("content"):
                continue
            session.add(VaultComment(
                entry_id=vault_entry.id,
                submitter=c.get("submitter", ""),
                date=c.get("date", ""),
                content=c.get("content", ""),
            ))

        # Add files
        for f in entry_data.get("files", []):
            session.add(VaultFile(
                entry_id=vault_entry.id,
                filepath=f.get("filepath", ""),
                filename=f.get("filename", ""),
                title=f.get("title", ""),
                description=f.get("description", ""),
                file_type=f.get("file_type", ""),
            ))

        # Add screenshots
        for s in entry_data.get("screenshots", []):
            session.add(VaultScreenshot(
                entry_id=vault_entry.id,
                filepath=s.get("filepath", ""),
                filename=s.get("filename", ""),
                thumb_src=s.get("thumb_src", ""),
            ))

        imported += 1

    # Update category count
    cat.entry_count = imported if not cat.entry_count else cat.entry_count + imported
    session.flush()

    return imported


def import_all(archive_dir: Path) -> dict[str, int]:
    """Import all XML data files from the archive into the database.

    Args:
        archive_dir: Path to the downloaded archive directory.

    Returns:
        Dict mapping "game/category" to number of entries imported.
    """
    results: dict[str, int] = {}

    with db_session() as session:
        # NWN1 categories
        for slug in NWN1_CATEGORIES:
            xml_path = archive_dir / "nwn1" / f"{slug}_data.xml"
            if not xml_path.exists():
                logger.debug(f"Skipping {xml_path} (not found)")
                continue

            logger.info(f"Parsing nwn1/{slug}_data.xml...")
            entries = parse_xml_file(xml_path)
            logger.info(f"Found {len(entries)} entries in nwn1/{slug}")

            count = import_category(session, "nwn1", slug, entries, archive_dir)
            results[f"nwn1/{slug}"] = count
            logger.info(f"Imported {count} entries for nwn1/{slug}")

        # NWN2 categories
        for slug in NWN2_CATEGORIES:
            xml_path = archive_dir / "nwn2" / f"{slug}_data.xml"
            if not xml_path.exists():
                logger.debug(f"Skipping {xml_path} (not found)")
                continue

            logger.info(f"Parsing nwn2/{slug}_data.xml...")
            entries = parse_xml_file(xml_path)
            logger.info(f"Found {len(entries)} entries in nwn2/{slug}")

            count = import_category(session, "nwn2", slug, entries, archive_dir)
            results[f"nwn2/{slug}"] = count
            logger.info(f"Imported {count} entries for nwn2/{slug}")

    total = sum(results.values())
    logger.info(
        f"Import complete: {total} total entries "
        f"across {len(results)} categories"
    )
    return results
