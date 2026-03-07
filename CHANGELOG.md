# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-03-07

### Added

#### Core bot
- Telegram bot built with `python-telegram-bot` 21.x (async)
- User whitelist via `ALLOWED_USER_IDS` environment variable — only listed Telegram IDs can interact with the bot
- Rate limiting per user (one search at a time, cooldown between requests)
- `/start` command with usage instructions
- Free-text book search: any message sent to the bot triggers a search
- Inline keyboard results list with title, format, and file size
- Non-EPUB result confirmation prompt before downloading

#### Search
- Parallel search across Anna's Archive and Prowlarr via `asyncio.gather`
- Anna's Archive: JSON API with automatic HTML scraping fallback
- Prowlarr: book category search (`7000`, `7020`) with support for direct and torrent results
- Results merged and deduplicated by normalized title, EPUB results ranked first
- Search capped at 10 results per source

#### Download
- Animated "preparing" dots while mirrors are being resolved
- `▰▰▱▱▱` streaming progress bar updated every 2 seconds once download starts
- Cancel button available during the entire download process
- Auto-retry: if a file exceeds the size limit, the bot silently tries the next result
- 50 MB file size limit enforced (Telegram default); extendable via local Bot API server
- Temp files cleaned up on error or cancellation; orphaned temp files purged at startup

#### Anna's Archive downloader
- Book page scraped for mirror links (libgen.rocks, libgen.li, library.lol, etc.)
- Intermediate HTML "ads" pages scraped to extract the real file link
- `slow_download` endpoint used as last-resort fallback
- HTML intermediate pages capped at 5 MB to prevent memory abuse

#### Prowlarr downloader
- Direct URL streaming for NZB/HTTP results
- Torrent grab via Prowlarr API (`/api/v1/download`)
- Download folder watcher (`watcher.py`) polls for the completed file by fuzzy title matching, with configurable timeout

#### Security
- SSRF protection on all outgoing HTTP requests: private, loopback, link-local, and reserved IP ranges are blocked
- SSRF protection on HTTP redirects via `httpx` response hook
- Admin-configured `ANNA_ARCHIVE_URL` allowed even on private networks (trusted origin)
- MD5 hashes validated with strict regex before use
- File extensions sanitized to alphanumeric characters only
- Downloaded URLs with `.onion` domains rejected
- Content-type validation on direct downloads
- Downloaded file size enforced chunk-by-chunk during streaming
- Query length capped to prevent abuse

#### Configuration
- All settings via `.env` file (`python-dotenv`)
- Anna's Archive URL: optional, leave empty to disable
- Prowlarr URL + API key: optional, leave empty to disable
- Both sources are independent — one, both, or neither can be active
- Optional local Telegram Bot API server support for files > 50 MB (`LOCAL_API_SERVER`, `LOCAL_API_ID`, `LOCAL_API_HASH`)
- Configurable torrent download timeout (`DOWNLOAD_TIMEOUT_MINUTES`, default 15 min)
- Configurable books download path (`BOOKS_DOWNLOAD_PATH`)

#### Deployment
- Docker Compose setup with optional `telegram-bot-api` sidecar for large file support
- `lancer.bat` one-click launcher for Windows users (installs dependencies, starts bot)
- `.env.example` template with inline documentation

#### Documentation
- `README.md` — technical setup guide in English (Python and Docker install paths)
- `LISEZMOI.md` — beginner-friendly French setup guide (no terminal required)
- `CLAUDE.md` — developer guide for working with Claude Code on this project
