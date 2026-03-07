import asyncio
import glob
import logging
import os
import re
import tempfile
import time

from dotenv import load_dotenv
load_dotenv()  # Must be called before imports that read env vars at module load time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import anna_archive
import prowlarr
import downloader
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Warn about non-numeric values in ALLOWED_USER_IDS
for _uid in os.environ.get("ALLOWED_USER_IDS", "").split(","):
    _uid = _uid.strip()
    if _uid:
        try:
            int(_uid)
        except ValueError:
            logger.warning(f"ALLOWED_USER_IDS: ignoring non-numeric value {_uid!r}")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ALLOWED_USER_IDS: set[int] = set()
for _uid in os.environ.get("ALLOWED_USER_IDS", "").split(","):
    _uid = _uid.strip()
    if _uid:
        try:
            ALLOWED_USER_IDS.add(int(_uid))
        except ValueError:
            pass  # sera loggé après l'init du logger
LOCAL_API_SERVER = os.environ.get("LOCAL_API_SERVER", "").rstrip("/")
MAX_RESULTS = 10
MAX_FILE_SIZE = 400 * 1024 * 1024 if LOCAL_API_SERVER else 50 * 1024 * 1024
MAX_QUERY_LENGTH = 200
RATE_LIMIT_SECONDS = 5
_CANCEL_KB = InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Annuler", callback_data="cancel_dl")]])


def _fmt_size(size_bytes: int) -> str:
    if not size_bytes:
        return "?"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} Ko"
    return f"{size_bytes / 1024 / 1024:.1f} Mo"


def _cleanup_orphaned_temp_files() -> None:
    pattern = os.path.join(tempfile.gettempdir(), "maman_*")
    count = 0
    for path in glob.glob(pattern):
        try:
            os.remove(path)
            count += 1
        except Exception:
            pass
    if count:
        logger.info(f"Cleaned up {count} orphaned temp file(s)")


def _is_allowed(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in ALLOWED_USER_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "👋 Bonjour ! Envoie-moi le titre d'un livre et je le chercherai pour toi.\n\n"
        "Je cherche sur Anna's Archive et Prowlarr. "
        "Tu pourras ensuite choisir le résultat à télécharger."
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    now = time.monotonic()
    last = context.user_data.get("last_search_at", 0.0)
    if now - last < RATE_LIMIT_SECONDS:
        await update.message.reply_text(f"⏳ Attends {RATE_LIMIT_SECONDS} secondes entre deux recherches.")
        return
    context.user_data["last_search_at"] = now

    query = update.message.text.strip()
    if not query:
        return

    if len(query) > MAX_QUERY_LENGTH:
        await update.message.reply_text(f"❌ Requête trop longue (max {MAX_QUERY_LENGTH} caractères).")
        return

    msg = await update.message.reply_text(f'🔍 Recherche en cours...')

    # Search Anna's Archive and Prowlarr in parallel
    aa_results, pr_results = await asyncio.gather(
        _safe_search(anna_archive.search, query, "Anna's Archive"),
        _safe_search(prowlarr.search, query, "Prowlarr"),
    )

    # Log raw results
    logger.info(f"=== Results for '{query}' ===")
    logger.info(f"Anna's Archive ({len(aa_results)}):")
    for r in aa_results:
        logger.info(f"  [AA] {r.get('title')!r} — {r.get('ext')} — {_fmt_size(r.get('size_bytes',0))} — md5={r.get('md5')}")
    logger.info(f"Prowlarr ({len(pr_results)}):")
    for r in pr_results:
        logger.info(f"  [PR] {r.get('title')!r} — {r.get('ext')} — {_fmt_size(r.get('size_bytes',0))} — torrent={r.get('is_torrent')}")

    # Merge: epub first, then other formats — direct before torrents — drop oversized
    def _sort_key(r):
        return (
            0 if r.get("ext") == "epub" else 1,
            0 if not r.get("is_torrent") else 1,
        )

    direct = [r for r in aa_results + pr_results if not r.get("is_torrent")]
    torrents = [r for r in pr_results if r.get("is_torrent")]
    all_results = sorted(direct, key=_sort_key) + torrents
    filtered = [r for r in all_results if not (r.get("size_bytes", 0) > MAX_FILE_SIZE)]

    # Deduplicate by normalized title — keep first (best) occurrence per title
    # Use first 35 chars to catch slight title variants
    seen_titles: set[str] = set()
    results = []
    for r in filtered:
        norm = re.sub(r"[^\w]", "", (r.get("title") or "")).lower()[:35]
        if norm and norm in seen_titles:
            continue
        if norm:
            seen_titles.add(norm)
        results.append(r)
        if len(results) >= MAX_RESULTS:
            break

    skipped = len(all_results) - len(results)
    logger.info(f"Merged total: {len(results)} result(s) ({skipped} excluded/deduplicated)")

    # Check if there are epub results
    has_epub = any(r.get("ext") == "epub" for r in results)
    epub_only_results = [r for r in results if r.get("ext") == "epub"]
    non_epub_results = [r for r in results if r.get("ext") != "epub"]

    if not results:
        await msg.edit_text(
            f'😕 Aucun résultat trouvé pour « {query} ».\nEssaie un autre titre ou orthographe.'
        )
        return

    # If no epub at all, ask user if PDF/other is OK
    if not has_epub and non_epub_results:
        exts = list({r.get("ext", "?") for r in non_epub_results})
        ext_str = ", ".join(exts).upper()
        context.user_data["results"] = results
        context.user_data["pending_non_epub"] = True
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ Oui, envoie-moi en {ext_str}", callback_data="confirm_non_epub")],
            [InlineKeyboardButton("❌ Non, annuler", callback_data="cancel_search")],
        ])
        await msg.edit_text(
            f"📚 Pas d'epub disponible pour « {query} ».\n"
            f"J'ai trouvé {len(results)} résultat(s) en {ext_str}. Ça ira ?",
            reply_markup=keyboard,
        )
        return

    context.user_data["results"] = results

    buttons = []
    for i, r in enumerate(results):
        if r.get("ext") != "epub" and has_epub:
            continue  # hide non-epub when epub exists
        icon = "📥" if not r.get("is_torrent") else "🌀"
        title = r.get("title") or "?"
        author = r.get("author") or ""
        title_short = title[:45] + "…" if len(title) > 45 else title
        label = f"{icon} {title_short}"
        if author:
            label += f" – {author[:20]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"dl_{i}")])

    keyboard = InlineKeyboardMarkup(buttons)
    n = len(buttons)
    await msg.edit_text(
        f"📚 {n} résultat{'s' if n > 1 else ''} trouvé{'s' if n > 1 else ''} :",
        reply_markup=keyboard,
    )


async def _safe_search(fn, query: str, source_name: str) -> list[dict]:
    try:
        return await fn(query)
    except Exception as e:
        logger.warning(f"{source_name} search error: {e}")
        return []


async def _animate_preparing(query, title: str, started: asyncio.Event, reply_markup=None) -> None:
    """Show animated dots until streaming starts or task is cancelled."""
    frames = ["⏳ Recherche du fichier .", "⏳ Recherche du fichier ..", "⏳ Recherche du fichier ..."]
    i = 0
    try:
        while not started.is_set():
            try:
                await query.edit_message_text(frames[i % len(frames)], reply_markup=reply_markup)
            except Exception:
                pass
            i += 1
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass


async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    data = query.data or ""
    if not data.startswith("dl_"):
        return

    try:
        idx = int(data[3:])
    except ValueError:
        return

    results = context.user_data.get("results", [])
    if idx >= len(results):
        await query.edit_message_text("❌ Résultat expiré, refais une recherche.")
        return

    def _progress_bar(pct: int) -> str:
        filled = pct // 10
        return "▰" * filled + "▱" * (10 - filled)

    async def _try_download(start_idx: int) -> tuple[str, dict] | None:
        """Try results from start_idx onwards, return (file_path, result) or None."""
        for i in range(start_idx, len(results)):
            result = results[i]
            t = result.get("title") or "livre"
            ext = result.get("ext") or "epub"
            is_torrent = result.get("is_torrent", False)

            if i > start_idx:
                logger.info(f"Auto-retry on result {i}: {t!r}")
                await query.edit_message_text(f"🔄 Essai du résultat suivant : « {t} »...", reply_markup=_CANCEL_KB)

            if is_torrent:
                await query.edit_message_text(
                    f"🌀 Envoi vers le client torrent pour « {t} »...\n"
                    "⏳ Surveillance du dossier de téléchargement...",
                    reply_markup=_CANCEL_KB,
                )
            else:
                await query.edit_message_text(f"⏳ Préparation…", reply_markup=_CANCEL_KB)

            # Animated dots while mirrors are being resolved (before streaming begins)
            streaming_started = asyncio.Event()
            dots_task = asyncio.create_task(_animate_preparing(query, t, streaming_started, reply_markup=_CANCEL_KB))

            async def on_progress(downloaded: int, total: int, _t=t) -> None:
                if not streaming_started.is_set():
                    streaming_started.set()
                if total:
                    pct = min(int(downloaded / total * 100), 99)
                    bar = _progress_bar(pct)
                    await query.edit_message_text(
                        f"⬇️ « {_t} »\n"
                        f"{bar} {pct}%  ({_fmt_size(downloaded)} / {_fmt_size(total)})",
                        reply_markup=_CANCEL_KB,
                    )
                else:
                    await query.edit_message_text(
                        f"⬇️ « {_t} »\n{_fmt_size(downloaded)} téléchargés…",
                        reply_markup=_CANCEL_KB,
                    )

            dl_task = asyncio.create_task(
                downloader.download_result(result, progress_callback=None if is_torrent else on_progress, max_bytes=MAX_FILE_SIZE)
            )
            if is_torrent:
                while not dl_task.done():
                    await asyncio.sleep(30)
                    if not dl_task.done():
                        try:
                            await query.edit_message_text(
                                f"🌀 Toujours en attente pour « {t} »...\n⏳ Merci de patienter.",
                                reply_markup=_CANCEL_KB,
                            )
                        except Exception:
                            pass

            try:
                file_path = await dl_task
            except asyncio.CancelledError:
                dl_task.cancel()
                raise
            except TimeoutError:
                logger.warning(f"Timeout on result {i}, skipping")
                dots_task.cancel()
                continue
            except Exception as e:
                logger.warning(f"Result {i} failed ({e}), skipping")
                dots_task.cancel()
                continue
            finally:
                dots_task.cancel()

            size = os.path.getsize(file_path)
            if size > MAX_FILE_SIZE:
                logger.info(f"Result {i} too large ({_fmt_size(size)}), skipping")
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                continue

            return file_path, result

        return None

    download_task = asyncio.create_task(_try_download(idx))
    context.user_data["active_dl_task"] = download_task
    try:
        outcome = await download_task
    except asyncio.CancelledError:
        return  # message already updated by handle_cancel_download
    finally:
        context.user_data.pop("active_dl_task", None)

    if outcome is None:
        await query.edit_message_text(
            "😕 Aucun résultat disponible dans la limite de taille.\nRefais une recherche."
        )
        return

    file_path, result = outcome
    title = result.get("title") or "livre"
    ext = result.get("ext") or "epub"

    try:

        safe_title = re.sub(r'[^\w\s\-]', '', title).strip()[:60] or "livre"
        filename = f"{safe_title}.{ext}"
        await query.edit_message_text(f"📤 Envoi de « {title} »...")

        with open(file_path, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=filename,
                caption=f"📖 {title}",
            )

        await query.edit_message_text(f"✅ Envoyé ! Bonne lecture 📖")
    finally:
        # Clean up temp file (not the watcher path — owned by the download client)
        if file_path and file_path.startswith(tempfile.gettempdir()):
            try:
                os.remove(file_path)
            except Exception:
                pass


async def handle_confirm_non_epub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_allowed(update):
        return
    results = context.user_data.get("results", [])
    if not results:
        await query.edit_message_text("❌ Résultat expiré, refais une recherche.")
        return
    # Show buttons for all results
    buttons = []
    for i, r in enumerate(results):
        icon = "📥" if not r.get("is_torrent") else "🌀"
        title_short = (r.get("title") or "?")[:40]
        ext = r.get("ext") or "?"
        size = _fmt_size(r.get("size_bytes", 0))
        buttons.append([InlineKeyboardButton(f"{icon} {title_short} — {ext} — {size}", callback_data=f"dl_{i}")])
    await query.edit_message_text(
        "📚 Choisis un résultat :",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_cancel_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_allowed(update):
        return
    task = context.user_data.pop("active_dl_task", None)
    if task and not task.done():
        task.cancel()
        await query.edit_message_text("⛔ Téléchargement annulé.")
    else:
        await query.edit_message_text("⛔ Aucun téléchargement en cours.")


async def handle_cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("results", None)
    await query.edit_message_text("🔍 Recherche annulée. Envoie un nouveau titre quand tu veux !")


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    builder = Application.builder().token(TELEGRAM_TOKEN)
    if LOCAL_API_SERVER:
        builder = (
            builder
            .base_url(f"{LOCAL_API_SERVER}/bot")
            .base_file_url(f"{LOCAL_API_SERVER}/file/bot")
            .local_mode(True)
        )
        logger.info(f"Local Bot API mode: {LOCAL_API_SERVER} (limit {MAX_FILE_SIZE // 1024 // 1024} MB)")
    app = builder.build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)
    )
    app.add_handler(CallbackQueryHandler(handle_download, pattern=r"^dl_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_confirm_non_epub, pattern=r"^confirm_non_epub$"))
    app.add_handler(CallbackQueryHandler(handle_cancel_search, pattern=r"^cancel_search$"))
    app.add_handler(CallbackQueryHandler(handle_cancel_download, pattern=r"^cancel_dl$"))

    _cleanup_orphaned_temp_files()
    if os.environ.get("ANNA_ARCHIVE_URL", "").startswith("http://"):
        logger.warning("ANNA_ARCHIVE_URL uses unencrypted HTTP — HTTPS is recommended")
    logger.info("Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
