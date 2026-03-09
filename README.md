# maman-books

> 🇫🇷 Une version ultra-friendly en français avec un tutoriel pas à pas est disponible ici : [LISEZMOI.md](./LISEZMOI.md)

A Telegram bot that searches and downloads ebooks on demand. Send it a book title, pick a result, get the file.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-zoeillle-ffdd00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/zoeillle)

> **Disclaimer:** This project is for educational purposes only. It is a technical demonstration of Telegram bot development, async Python, and API integration. The author takes no responsibility for how others configure or use this software. Users are solely responsible for ensuring their use complies with the laws of their country and the terms of service of any third-party service they connect to.

## Prerequisites

- Python 3.11+ **or** Docker + Docker Compose
- A Telegram account

---

## Step 1 — Create your Telegram bot

### 1.1 Talk to BotFather

BotFather is the official Telegram bot that lets you create and manage bots.

1. Open Telegram (desktop or mobile)
2. In the search bar, search for **@BotFather** and open the chat
3. Send the command `/newbot`

BotFather will ask you two things:

- **Name** — the display name of your bot, shown in chats (e.g. `My Book Bot`)
- **Username** — must be unique and end with `bot` (e.g. `my_book_bot`)

Once done, BotFather replies with a message containing your **bot token**, which looks like this:

```
123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Copy it — you'll need it in the `.env` file.

### 1.2 Find your Telegram user ID

The bot uses a whitelist to restrict who can use it. You need to add your own numeric Telegram ID.

1. In Telegram, search for **@userinfobot** and open the chat
2. Send any message (e.g. `/start`)
3. It replies with your info, including your **Id** (a number like `123456789`)

Copy that number — it goes in `ALLOWED_USER_IDS` in the `.env`.

If you want to allow other people, ask them to do the same and give you their ID. You can add multiple IDs separated by commas.

---

## Step 2 — Download the project

```bash
git clone https://github.com/Zoeille/maman-books.git
cd maman-books
```

Or download and extract the ZIP from GitHub if you don't have git installed.

---

## Step 3 — Configure the environment

Copy the example config file:

```bash
cp .env.example .env
```

Then open `.env` in any text editor and fill in the values:

```env
TELEGRAM_TOKEN=123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ALLOWED_USER_IDS=123456789
ANNA_ARCHIVE_URL=
```

**Required variables:**

| Variable | Description |
|---|---|
| `TELEGRAM_TOKEN` | The token you got from BotFather in Step 1.1 |
| `ALLOWED_USER_IDS` | Your Telegram user ID from Step 1.2. Multiple IDs: `111,222,333` |

**Optional — Anna's Archive:**

| Variable | Description |
|---|---|
| `ANNA_ARCHIVE_URL` | Base URL of the Anna's Archive instance to use. Leave empty to disable. |

**Optional — Prowlarr integration** (for torrent support and additional indexers):

| Variable | Description |
|---|---|
| `PROWLARR_URL` | URL of your Prowlarr instance, e.g. `http://localhost:9696`. Leave empty to disable. |
| `PROWLARR_API_KEY` | Found in Prowlarr under Settings → General → API Key |
| `BOOKS_DOWNLOAD_PATH` | The folder where your torrent client saves completed downloads |
| `DOWNLOAD_TIMEOUT_MINUTES` | How long to wait for a torrent to finish (default: `15`) |

Both sources are optional and independent — you can enable one, the other, or both. At least one must be configured for the bot to return results.

**Optional — Format & conversion:**

| Variable | Description |
|---|---|
| `ALLOWED_FORMATS` | Comma-separated list of formats to offer. Accepted values: `epub`, `pdf`, `mobi`, `azw3`. Default: `epub,pdf`. If only one value is set, no format question is asked. Kindle models from 2022 onward support EPUB natively — MOBI/AZW3 are mainly needed for older Kindles. |
| `USER_PREFS_FILE` | Path to the JSON file that stores per-user preferences (format, email, Kindle address). Default: `user_prefs.json` (next to `bot.py`). Set to `data/user_prefs.json` to keep it in the `data/` folder. |

Format selection only applies to epub results. The bot always downloads EPUB and converts on the fly:
- **→ PDF**: PyMuPDF (no extra dependency required)
- **→ MOBI / AZW3**: Calibre's `ebook-convert` if installed, otherwise PyMuPDF as fallback

**Optional — Calibre (for accurate MOBI/AZW3 conversion):**

Install [Calibre](https://calibre-ebook.com) on the machine running the bot. No configuration needed — the bot auto-detects `ebook-convert` in your PATH. Without Calibre, MOBI/AZW3 conversion falls back to PyMuPDF (output may vary).

The startup log shows whether Calibre was found:
```
  Calibre        : ✓ ebook-convert trouvé
```

**Optional — Email & Send to Kindle:**

The bot can send books directly to an email address or to a Kindle. Each user stores their own email/Kindle address via `/settings`.

| Variable | Description |
|---|---|
| `SMTP_HOST` | SMTP server hostname. Default: `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port. Default: `587` (STARTTLS) |
| `SMTP_USER` | SMTP login (e.g. your Gmail address) |
| `SMTP_PASSWORD` | SMTP password. For Gmail, generate an **App Password** at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (do not use your regular password) |
| `SMTP_FROM` | Sender address. Defaults to `SMTP_USER` if left empty |

> **Send to Kindle:** add the `SMTP_FROM` address to your Amazon account's "Approved Personal Document E-mail List" (Amazon account → Manage Your Content and Devices → Preferences → Personal Document Settings).

SMTP is global (set once in `.env`). Each user sets their own destination address with `/settings`.

**Optional — VirusTotal** (scans downloaded files before sending):

| Variable | Description |
|---|---|
| `VIRUSTOTAL_API_KEY` | Your VirusTotal API key. Leave empty to disable. Free tier supports up to 4 requests/min. Files larger than 32 MB are skipped. |

To get a free API key:
1. Create an account at [virustotal.com](https://www.virustotal.com)
2. Go to your profile (top-right) → **API key**
3. Copy the key and paste it as `VIRUSTOTAL_API_KEY` in your `.env`

The free tier is sufficient for personal use. The bot checks by file hash first — if VirusTotal already knows the file, no upload is needed and the result is near-instant.

**Optional — Update notifications:**

| Variable | Description |
|---|---|
| `GITHUB_REPO` | GitHub repository to watch for new releases, in `owner/repo` format. Defaults to `Zoeille/maman-books`. Set to empty to disable. |

**Optional — Local Bot API server** (only needed if you want to send files larger than 50 MB):

| Variable | Description |
|---|---|
| `LOCAL_API_SERVER` | URL of the local Bot API server (see below) |
| `LOCAL_API_ID` | API ID from [my.telegram.org](https://my.telegram.org) |
| `LOCAL_API_HASH` | API Hash from [my.telegram.org](https://my.telegram.org) |

By default Telegram limits file uploads to 50 MB. If you need more, see the Docker section below.

---

## Step 4a — Run directly with Python

```bash
# Install dependencies
pip install -r requirements.txt

# Start the bot
python bot.py
```

The bot will start and print its active configuration, then log `Bot started.` when ready:

```
--- maman-books v1.2.0 ---
  Anna's Archive : ✓ https://…
  Prowlarr       : ✗ désactivé
  Formats        : epub, pdf, mobi, azw3
  VirusTotal     : ✓ activé
  Calibre        : ✓ ebook-convert trouvé
  Email / Kindle : ✓ activé
  Mises à jour   : ✓ Zoeille/maman-books
  Limite fichier : 50 MB
  Utilisateurs   : 1 autorisé(s)
Bot started.
```

Open Telegram, find your bot by its username, and send `/start`.

To keep it running in the background on Linux/macOS:

```bash
nohup python bot.py &
```

---

## Step 4b — Run with Docker

Make sure Docker and Docker Compose are installed.

A pre-built image is available at **`ghcr.io/zoeille/maman-books:latest`** — no need to build locally.

### Without local Bot API (50 MB file limit)

Edit `docker-compose.yml` and remove the `depends_on` block and the `telegram-bot-api` service — they are only needed for the local API server.

Then run:

```bash
docker compose up -d bot
```

Check the logs to confirm it's running:

```bash
docker compose logs -f bot
```

### With local Bot API server (no file size limit)

This requires registering your app on Telegram's developer platform:

1. Go to [my.telegram.org](https://my.telegram.org) and log in with your Telegram account
2. Click **API development tools**
3. Fill in the form (App title and Short name can be anything)
4. You'll get an **App api_id** and **App api_hash**

Add them to your `.env`:

```env
LOCAL_API_SERVER=http://telegram-bot-api:8081
LOCAL_API_ID=12345678
LOCAL_API_HASH=abcdef1234567890abcdef1234567890
```

Then start everything:

```bash
docker compose up -d --build
docker compose logs -f bot
```

> **User preferences** are stored in `./data/user_prefs.json` on the host (bind-mounted into the container). The `data/` folder is created automatically on first run. Make sure to set `USER_PREFS_FILE=data/user_prefs.json` in your `.env`.

---

## Usage

1. Open Telegram and find your bot by its username
2. Send `/start` — on first launch, a setup wizard guides you through your preferences (default format, email, Kindle address)
3. Type any book title and send it
4. The bot searches and shows a list of results — tap one to download
5. If `ALLOWED_FORMATS` has multiple values, you'll be asked which format you want
6. If you've configured an email or Kindle address, you'll be asked where to send it (Telegram / Email / Kindle)
7. The file is sent — if VirusTotal is enabled, it's scanned first

Use `/settings` at any time to update your preferences (format, email, Kindle address).

---

## Troubleshooting

- **"All download sources unavailable"** — your ISP's DNS may be blocking download servers (Libgen, etc.). Switch to a public DNS such as Cloudflare (`1.1.1.1`) or Google (`8.8.8.8`). When running in Docker, you can set this in `docker-compose.yml`:
  ```yaml
  services:
    bot:
      dns:
        - 1.1.1.1
        - 8.8.8.8
  ```
  For French users, a step-by-step guide is available in [LISEZMOI.md](./LISEZMOI.md).
