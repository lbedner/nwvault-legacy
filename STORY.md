# Bringing Back the NWVault

## What was nwvault.ign.com?

The Neverwinter Vault was the central hub for the Neverwinter Nights modding community from 2002 to ~2013. Hosted by IGN's Vault Network, it was where thousands of module builders, scripters, model makers, and players shared their work. At its peak it held over 39,000 entries across 37 categories — modules, hakpaks, scripts, portraits, creatures, models, prefabs, sounds, textures, and more — for both NWN1 and NWN2. Every entry had ratings, comments, screenshots, and download files. The site had a Hall of Fame, staff reviews, community news, and a full navigation system. It was the place.

The site went down. The community scattered to neverwintervault.org (which hosts new content) and various forums. The old content — the modules from 2002-2013, the comments, the reviews, the scores — was gone from the web.

## The Backup

Before the site died, someone (meaglyn / Phil Auld) wrote a Java scraper (`VaultParser`) that crawled every entry page and saved it. The full backup landed at `neverwintervault.org/rolovault/` — a Caddy directory listing with the entire archive. Every entry's original HTML page, metadata XML, screenshots, and download files were preserved. The category-level `*_data.xml` files contained all entries with their metadata, comments, scores, and file listings in structured XML.

## What We Did

### 1. Scraped the Archive
Built a downloader that fetches the file listing from rolovault, filters out mod binaries (the .zip/.7z/.hak files would be hundreds of GB), and downloads everything else — 136,629 files totaling ~21GB. HTML pages, XML metadata, screenshot images, all preserved with the original directory structure.

### 2. Parsed Catastrophically Bad XML
The XML files declare UTF-8 encoding but are actually Latin-1. They contain bare `&` characters in attribute values (`fieldname="Tricks&Traps"`), bare `<` in text content (`<1 to 1`), undefined HTML entities (`&nbsp;`), and user-generated content from 2002 with every encoding crime imaginable. Standard XML parsers refuse to touch them.

We used lxml with `recover=True` after pre-cleaning: decode as Latin-1, replace HTML entities, escape bare ampersands and angle brackets, strip control characters. The result: 39,476 entries and 207,535 comments successfully imported into a SQLite database.

### 3. Served the Original HTML
The archived pages are the actual nwvault.ign.com HTML — complete with the IGN header, Neverwinter Nights 2 Vault logo, left sidebar with expandable menus, right sidebar with Hall of Fame and Top Modules lists, and the full entry content with comments. We serve them directly through FastAPI at `/vault/{game}/{category}/{id}/`.

### 4. Fixed 45,000 Pages of Dead URLs
Every page referenced CSS, JavaScript, and images from `vnmedia.ign.com`, `vaultnap.ign.com`, and `common.ignimgs.com` — all dead domains. Internal links pointed to `View.php?view=Modules.Detail&id=123` — a PHP controller that no longer exists. Screenshot thumbnails pointed to IGN's CDN.

We built an HTML fixer that runs across all 45,000 pages:
- Rewrites dead asset URLs to locally-served copies (downloaded from the Wayback Machine using the `id_` flag for raw files)
- Maps `View.php?view=X.Detail&id=Y` links to our archive routes
- Converts thumbnail URLs to local fullres images
- Fixes URLs inside CSS and JS files that reference dead domains
- Falls back to the Wayback Machine for anything not available locally

### 5. Downloaded Shell Assets from the Wayback Machine
The ~60 CSS, JS, and image files that make up the vault's look — the header banner, sidebar background textures, menu icons, stylesheets — were downloaded from `web.archive.org` using the `id_` URL flag (which returns the raw file, not the Wayback toolbar wrapper). These serve locally at `/_assets/` for instant page loads.

### 6. Built the View.php Controller
The original site routed everything through `View.php`. We recreated this as a FastAPI route that handles the same URL patterns:
- `View.php?view=Modules.Detail&id=5208` → redirects to the archived page
- `View.php?view=Modules.List` → renders a listing from the database
- `View.php?view=Modules.HOF` → Hall of Fame
- `View.php?view=LatestAdditions&clusters=modules` → recent entries
- `View.php?view=GlobalSearch&q=dragon` → search results
- Unknown views → redirect to Wayback Machine

Also `fms/TopRated.php?content=modules` for Top Rated pages.

The rendered pages use the same page shell (header, sidebar, footer) extracted from an archived page, and the same CSS classes (`fmstborder`, `fmsalt1`, `fmsalt2`, `fmstheader`) so they look identical to the original.

### 7. Worker Infrastructure
All maintenance tasks run through arq worker queues with a Redis broker:
- **vault_download** — fetches files from rolovault
- **vault_import** — parses XML and imports to database
- **vault_fix** — rewrites URLs in archived HTML

Each queue has its own Docker container, visible in the Overseer dashboard with real-time progress, success rates, and error details. Tasks are chunked by category (~37 jobs per run) for granular tracking.

### 8. API
Full REST API at `/api/v1/vault/`:
- Browse entries by category with pagination and sorting
- Search across titles and descriptions
- Top rated entries
- Category listing with entry counts
- Individual entry detail with comments, files, and screenshots
- Overall statistics

## The Stack

Built with [Aegis Stack](https://github.com/lbedner/aegis-stack):
- **FastAPI** — web server and API
- **SQLModel/SQLAlchemy** — ORM with SQLite
- **lxml** — tolerant XML parsing
- **arq + Redis** — background worker queues
- **Flet** — Overseer dashboard
- **Docker Compose** — all services orchestrated

## What's There

- 39,476 vault entries (35,079 NWN1 + 4,397 NWN2)
- 207,535 comments
- 37 categories
- 44,732 archived HTML pages
- 46,227 images
- ~21GB of preserved content
- Full-text search
- Working navigation between entries
- Original vault look and feel

## What's Next

- Wayback Machine scrape for the review/rating pages (per-user scored reviews exist at `View.php?view=Ratings.Viewer&id=X`)
- Template-based page rendering (replace static HTML serving with DB-driven templates, like the original PHP did)
- Production deployment to a US East server
- Download file links pointing to rolovault
- CDN for static assets

## Why

Because The Rose of Eternity — Chapter 2 — Cry the Beloved deserves to be at #2 on the Hall of Fame where it belongs. And so does everything else the community built.
