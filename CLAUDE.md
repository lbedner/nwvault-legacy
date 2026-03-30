# CLAUDE.md — NWVault Legacy

## Project Overview
Rebuilding nwvault.ign.com from the rolovault archive backup. Serves original archived HTML pages with a FastAPI backend, SQLite database, and arq worker infrastructure.

## Architecture Decisions

### Serve original HTML, don't build custom frontend
The user is not a frontend developer. The archived HTML pages from nwvault.ign.com ARE the product. Don't propose Jinja2 templates, React, or any custom UI unless explicitly asked. The only generated pages are listing/navigation pages (Top Rated, Search, etc.) that use the vault's original CSS classes.

### Worker task design: one job per unit of work
Every worker task should be granular — one entry, one category, not "process everything in a loop." If a job fails, only that unit fails. The orchestrator pattern: check the DB for what's missing, enqueue individual jobs.

Bad: `scrape_all_reviews()` — one giant loop, if Wayback blocks at entry 50, entries 51-500 never get scraped
Good: `enqueue_review_scrape()` checks DB → enqueues N `scrape_review()` jobs, one per entry

### Avoid N+1 queries
Use `WHERE id IN (...)` or `DISTINCT` queries to batch-check existence. Don't loop through entries checking one at a time.

### Wayback Machine rate limiting
Wayback blocks after ~30 rapid requests. Use delays (1.5-3s between requests). Use `id_` flag in URLs for raw file content (not `im_` which returns HTML wrapper). Individual jobs handle this naturally since arq spaces them out.

### Asset URL strategy
- Shell assets (CSS, JS, header images): downloaded locally, served at `/_assets/`
- Per-entry screenshots: served from `/vault/{game}/{category}/{id}/` (archive directory)
- Anything not available locally: falls back to Wayback Machine
- CSS/JS files themselves may contain URLs that need fixing too

## Tech Stack
- **Aegis Stack** scaffolding (FastAPI, Flet dashboard, arq workers)
- **lxml** with `recover=True` for parsing catastrophically broken XML
- **SQLite** via SQLModel/SQLAlchemy
- **arq + Redis** for background workers
- Three vault worker queues: `vault_download`, `vault_import`, `vault_fix`

## Key Paths
- `app/models/vault.py` — VaultEntry, VaultComment, VaultFile, VaultScreenshot, VaultReview, VaultCategory
- `app/services/vault/` — downloader, importer, html_fixer, renderer, review_scraper
- `app/components/backend/api/viewphp.py` — View.php controller (legacy URL routing)
- `app/components/backend/api/archive.py` — serves archived HTML pages
- `app/components/backend/api/admin.py` — admin API for triggering worker jobs
- `app/components/worker/queues/vault_*.py` — three worker queue configs
- `archive/` — downloaded archive files (21GB, gitignored)
- `archive/assets/` — cached shell assets from Wayback

## Commands
```bash
# CLI
nwvault-legacy vault pipeline      # Download XMLs + import to DB
nwvault-legacy vault download      # Download HTML + images from rolovault
nwvault-legacy vault fix-html      # Fix broken URLs in archived HTML
nwvault-legacy vault stats         # Show archive + DB stats

# API triggers (enqueue to workers)
POST /admin/import/pipeline        # Full pipeline via workers
POST /admin/import/xml             # Import XML to DB
POST /admin/import/download        # Download HTML + images
POST /admin/import/fix-html        # Fix HTML URLs
POST /admin/import/scrape-reviews  # Scrape reviews from Wayback
```

## Don't
- Don't use `sed` on source files (wiped viewphp.py once)
- Don't assume Wayback Machine files are real — verify they're not HTML error pages
- Don't build custom frontend/templates unless asked
- Don't run everything in one giant loop — use granular worker jobs
