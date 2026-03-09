# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.1] — 2026-03-09

### Fixed

- `prefs.py`: default path for `user_prefs.json` now resolves relative to the script directory (`__file__`) instead of the current working directory — the file is always created next to `bot.py` regardless of where the bot is launched from.
- `docker-compose.yml`: `USER_PREFS_FILE=data/user_prefs.json` is now injected directly via the `environment` block instead of relying on `.env` — Docker users no longer need to set this variable manually.
- Removed `USER_PREFS_FILE` from `.env.example` (and `.env`) — Python users never need to set it.
- `prefs.py`: temp file for atomic write now created in the same directory as `PREFS_FILE` — fixes `OSError: [Errno 18] Invalid cross-device link` in Docker where `/tmp` and the bind-mounted `data/` folder are on different filesystems.

### Changed

- Anna's Archive: removed JSON API attempt (`/search.json` always returns 404) — search now goes directly to HTML scraping.

### CI/CD

- GitHub Actions workflow now triggers on version tags (`v*`) instead of pushes to `main`.
- Docker images are tagged with the full semver (`1.2.1`), major.minor (`1.2`), and `latest`.

---

## [1.2.0] — 2026-03-09

### Added

- **MOBI & AZW3 formats** — epub results can now be converted to MOBI or AZW3 before sending. Conversion uses Calibre's `ebook-convert` if installed; falls back to PyMuPDF otherwise. MOBI/AZW3 are mainly needed for Kindle models older than 2022 — newer Kindles support EPUB natively.
- **Email delivery** (`mailer.py`) — books can be sent to any email address via SMTP (stdlib `smtplib`, no extra dependencies). Configured globally via `SMTP_HOST/PORT/USER/PASSWORD/FROM` in `.env`.
- **Send to Kindle** — variant of email delivery where the subject is set to `"convert"`, triggering Amazon's automatic format conversion. The sender address must be whitelisted in the Amazon account's approved document email list.
- **User preferences** (`prefs.py`) — per-user settings stored in a JSON file (`USER_PREFS_FILE`). Stores preferred format, personal email, and Kindle address. Async-safe with atomic writes via `os.replace()`.
- **`/settings` command** — inline menu to view and update preferences (format, email, Kindle address, delete all data).
- **Onboarding wizard** — on first `/start`, a step-by-step flow guides new users through setting up their format, email, and Kindle preferences.
- **Destination menu** — after choosing a format, users with a configured email or Kindle address are offered a delivery choice: Telegram / Email / Kindle.
- **Calibre auto-detection** — the bot detects `ebook-convert` in PATH at startup and logs whether Calibre is available.

### Changed

- `ALLOWED_FORMATS` now accepts `mobi` and `azw3` in addition to `epub` and `pdf`.
- Download flow: the bot always fetches the best available EPUB, then converts to the requested format post-download (rather than searching for a specific format).
- Cancel button is now responsive during downloads (non-blocking loop with 0.5 s timeout slices instead of a single blocking `await`).
- SMTP errors shown to the user are now generic (details logged server-side only).
- Startup log now shows Calibre and Email/Kindle status.
- Version bump to `1.2.0`.

### Fixed

- `NameError: name 'update' is not defined` in `_do_download` when sending via email/Kindle — replaced `update.effective_user.id` with `query.from_user.id`.

### Security

- `user_prefs.json` added to `.gitignore` (contains user email addresses).

### Deployment

- `docker-compose.yml`: added `./data:/app/data` bind mount so user preferences survive container restarts.
- `docker-compose.yml`: removed the external `media-stack` network — the bot only needs the internal network to reach the `telegram-bot-api` sidecar.
- `USER_PREFS_FILE=data/user_prefs.json` added to `.env.example`.

---

## [1.1.1] — 2026-03-07

### Fixed

- Better error message when all download mirrors are unavailable: now distinguishes between mirror failures and file size limit exceeded.

### Documentation

- `LISEZMOI.md`: added DNS troubleshooting tip — ISP DNS can block download servers (Libgen, etc.), with a link to a guide for changing DNS on Windows.

---

## [1.1.0] — 2026-03-07

### Added

- **PDF conversion** — epub results can now be sent as PDF. Powered by PyMuPDF (`pymupdf`), no system dependencies required. The format choice (EPUB / PDF) is shown as inline buttons before downloading; if only one format is configured the question is skipped.
- **`ALLOWED_FORMATS` env var** — controls which formats are offered (`epub`, `pdf`, or both). Defaults to `epub,pdf`.
- **VirusTotal integration** (`virustotal.py`) — downloaded files are scanned before being sent. Checks by SHA-256 hash first (avoids redundant uploads for known files), then uploads and polls for the result. Malicious files are blocked; suspicious files are sent with a warning in the caption; scan errors result in a caption warning without blocking the file. Disabled when `VIRUSTOTAL_API_KEY` is absent. The scanning message shows animated dots so the user knows it's in progress.
- **Automatic update notifications** — on startup and every 24 hours, the bot checks the latest GitHub release and notifies all allowed users via Telegram if a newer version is available. Controlled by `GITHUB_REPO` (defaults to `Zoeille/maman-books`). Notifications are deduplicated within a process run.

### Fixed

- `python-telegram-bot[job-queue]` extra now declared in `requirements.txt` — `JobQueue` was silently unavailable without it.

### Changed

- Merged the double loop over `ALLOWED_USER_IDS` at startup into a single pass.
- Bot logs its active configuration at startup (sources, formats, VirusTotal, update checks, file size limit, user count).

### Refactored

- `_is_safe_url` extracted to `utils.py` — was duplicated in `anna_archive.py` and `downloader.py`.
- `handle_download` split into `handle_download` (format selection) + `handle_download_fmt` + `_do_download` to separate concerns and avoid duplication.

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
