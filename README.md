# maman-books

> 🇫🇷 Une version ultra-friendly en français avec un tutoriel pas à pas est disponible ici : [LISEZMOI.md](./LISEZMOI.md)

A Telegram bot that searches and downloads ebooks on demand. Send it a book title, pick a result, get the file.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-zoeillle-ffdd00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/zoeillle)

> **Disclaimer:** This project is for educational purposes only. It is a technical demonstration of Telegram bot development, async Python, and API integration. The author takes no responsibility for how others configure or use this software. Users are solely responsible for ensuring their use complies with the laws of their country and the terms of service of any third-party service they connect to.

## Prerequisites

- Python 3.11+ **or** Docker + Docker Compose
- A Telegram account (for bot usage)

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

**Optional — Local Bot API server** (only needed if you want to send files larger than 50 MB):

| Variable | Description |
|---|---|
| `LOCAL_API_SERVER` | URL of the local Bot API server (see below) |
| `LOCAL_API_ID` | API ID from [my.telegram.org](https://my.telegram.org) |
| `LOCAL_API_HASH` | API Hash from [my.telegram.org](https://my.telegram.org) |

By default Telegram limits file uploads to 50 MB. If you need more, see the Docker section below.

---

## Step 4a — Run directly with Python

### Telegram Bot

```bash
# Install dependencies
pip install -r requirements.txt

# Start the bot
python bot.py
```

The bot will start and log `Bot started.` when ready. Open Telegram, find your bot by its username, and send `/start`.

To keep it running in the background on Linux/macOS:

```bash
nohup python bot.py &
```

---

## Step 4b — Run with Docker

Make sure Docker and Docker Compose are installed.

### Telegram Bot with Docker

#### Without local Bot API (50 MB file limit)

Edit `docker-compose.yml` and remove the `depends_on` block and the `telegram-bot-api` service — they are only needed for the local API server.

Then run:

```bash
docker compose up -d bot --build
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

> The `docker-compose.yml` uses an external Docker network called `media-stack`. If you don't have that network (e.g. you're not running an *arr stack), remove the `networks` section and the `media-stack` reference from `docker-compose.yml` before starting.

---

## Usage

### Telegram Bot

1. Open Telegram and find your bot by its username
2. Send `/start`
3. Type any book title and send it
4. The bot searches and shows a list of results — tap one to download
5. The file is sent directly in the chat

## Optional — Web interface

If you prefer, there is also a web interface available.

### Run with Python

```bash
pip install -r requirements.txt
python web_server.py
```

Then open `http://localhost:5000`.

### Run with Docker

```bash
docker network create media-stack
docker compose up -d web --build
docker compose logs -f web
```

### Web environment variables

| Variable | Description | Default |
|---|---|---|
| `WEB_HOST` | Host to bind the server to | `0.0.0.0` |
| `WEB_PORT` | Port to run the server on | `5000` |
| `WEB_DEBUG` | Enable Flask debug mode (`true` or `false`) | `false` |
| `FLASK_SECRET_KEY` | Secret key for Flask sessions (optional) | Auto-generated |

At least one of `ANNA_ARCHIVE_URL` or `PROWLARR_URL` must be configured.
