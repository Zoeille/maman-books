# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the bot

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python bot.py

# Run via Docker
docker compose up -d --build
docker compose logs -f bot
```

The bot process is long-running. When working locally during development, kill the background process before restarting: use `TaskStop` on the running task ID.

## Architecture

Single-process async bot (python-telegram-bot 21.x + httpx). No database — state lives in `context.user_data` per Telegram user session.

**Search flow:** `bot.py` fires `anna_archive.search()` and `prowlarr.search()` in parallel via `asyncio.gather`, merges results (epub-first, deduped by normalized title), stores them in `context.user_data["results"]`.

**Download flow:** User clicks a button → `downloader.download_result(result, progress_callback)` dispatches to:
- `anna_archive.download()` — scrapes the book's Anna's Archive page for mirror links, streams the first working one
- `downloader._download_direct()` — streams a Prowlarr direct URL
- `downloader._download_torrent()` — calls `prowlarr.grab()` then `watcher.wait_for_file()` polls the download folder

**Progress UX:** An `asyncio.Task` (`_animate_preparing`) shows animated dots while mirrors are being resolved. It is cancelled as soon as `on_progress` is first called (i.e. streaming has started), which then switches to a `▰▰▱▱▱` progress bar updated every 2 seconds.

**Auto-retry:** If a downloaded file exceeds `MAX_FILE_SIZE` (50 MB without local Bot API), the bot silently tries the next result in the list.

## Key constraints

- **Telegram 50 MB upload limit** — enforced via `MAX_FILE_SIZE`. Raising it requires a local `telegram-bot-api` server (`LOCAL_API_SERVER` env var + `LOCAL_API_ID`/`LOCAL_API_HASH` from my.telegram.org). Set `LOCAL_API_SERVER=http://telegram-bot-api:8081` when running in Docker.
- **Anna's Archive JSON API returns 404** — always falls back to HTML scraping of `annas-archive.gl/search`.
- **Mirror resolution is slow** — libgen.is is blocked in France; `libgen.li/ads.php` returns an intermediate HTML page that must be scraped for the real `get.php?key=` URL.
- **Whitelist** — every handler checks `ALLOWED_USER_IDS` from `.env`. Adding a user = append their numeric Telegram ID.

## Environment variables

See `.env.example`. Required: `TELEGRAM_TOKEN`, `ALLOWED_USER_IDS`. Optional but needed for torrents: `PROWLARR_URL`, `PROWLARR_API_KEY`, `BOOKS_DOWNLOAD_PATH`.
