import asyncio
import glob
import httpx
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
import converter
import virustotal
import prefs
import mailer
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ALLOWED_USER_IDS: set[int] = set()
for _uid in os.environ.get("ALLOWED_USER_IDS", "").split(","):
    _uid = _uid.strip()
    if _uid:
        try:
            ALLOWED_USER_IDS.add(int(_uid))
        except ValueError:
            logger.warning(f"ALLOWED_USER_IDS: ignoring non-numeric value {_uid!r}")
LOCAL_API_SERVER = os.environ.get("LOCAL_API_SERVER", "").rstrip("/")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Zoeille/maman-books")
_VALID_FORMATS = {"epub", "pdf", "mobi", "azw3"}
ALLOWED_FORMATS: list[str] = [
    f for f in (s.strip() for s in os.environ.get("ALLOWED_FORMATS", "epub,pdf").split(","))
    if f in _VALID_FORMATS
] or ["epub"]  # fallback si la valeur env est invalide
VERSION = "1.2.0"
MAX_RESULTS = 10
MAX_FILE_SIZE = 400 * 1024 * 1024 if LOCAL_API_SERVER else 50 * 1024 * 1024
MAX_QUERY_LENGTH = 200
RATE_LIMIT_SECONDS = 5
_CANCEL_KB = InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Annuler", callback_data="cancel_dl")]])
_notified_update: str | None = None  # tag already notified in this process run


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


def _is_newer_version(remote: str, local: str) -> bool:
    """Return True if remote tag is strictly greater than local version."""
    def parse(v: str) -> tuple:
        try:
            return tuple(int(x) for x in v.lstrip("v").split("."))
        except ValueError:
            return (0,)
    return parse(remote) > parse(local)


async def check_for_updates(context: ContextTypes.DEFAULT_TYPE) -> None:
    global _notified_update
    if not GITHUB_REPO:
        return
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "maman-books-bot"}) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
            )
            if resp.status_code == 404:
                return  # pas encore de release
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Update check failed: {e}")
        return

    tag = data.get("tag_name", "")
    if not tag or tag == _notified_update or not _is_newer_version(tag, VERSION):
        return

    _notified_update = tag
    url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")
    msg = (
        f"🆕 Nouvelle version disponible : *{tag}*\n"
        f"Version installée : `{VERSION}`\n"
        f"[Voir les changements]({url})"
    )
    for uid in ALLOWED_USER_IDS:
        try:
            await context.bot.send_message(uid, msg, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            logger.warning(f"Could not notify user {uid} about update: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    user_id = update.effective_user.id
    user_prefs = await prefs.get(user_id)

    # Si l'utilisateur n'a pas de préférences, lancer l'onboarding
    if not user_prefs:
        context.user_data["onboarding_step"] = "format"
        await handle_onboarding_format(update, context)
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Configurer mes préférences", callback_data="open_settings")],
    ])
    await update.message.reply_text(
        "👋 Bonjour ! Envoie-moi le titre d'un livre et je le chercherai pour toi.\n\n"
        "Je cherche sur Anna's Archive et Prowlarr. "
        "Tu pourras ensuite choisir le résultat à télécharger.",
        reply_markup=keyboard,
    )


async def handle_onboarding_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """First step of onboarding: choose format."""
    context.user_data["onboarding_step"] = "format"

    buttons = []
    for fmt in ["epub", "pdf", "mobi", "azw3"]:
        if fmt in ALLOWED_FORMATS:
            buttons.append([InlineKeyboardButton(f"{fmt.upper()}", callback_data=f"onb_fmt_{fmt}")])

    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "👋 Bienvenue ! Commençons par configurer tes préférences.\n\n"
        "📚 Quel format préfères-tu ?",
        reply_markup=keyboard,
    )


async def handle_onboarding_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Second step of onboarding: ask for email."""
    query = update.callback_query
    await query.answer()

    context.user_data["onboarding_step"] = "email"
    context.user_data["waiting_for"] = "onb_email"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Passer", callback_data="onb_skip_email")],
    ])
    await query.edit_message_text(
        "📧 Veux-tu configurer un email pour recevoir les livres ?\n\n"
        "Envoie ton adresse email (ou clique Passer pour continuer).",
        reply_markup=keyboard,
    )


async def handle_onboarding_kindle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Third step of onboarding: ask for Kindle email."""
    if update.callback_query:
        await update.callback_query.answer()

    context.user_data["onboarding_step"] = "kindle"
    context.user_data["waiting_for"] = "onb_kindle"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Passer", callback_data="onb_skip_kindle")],
    ])

    msg_text = (
        "📖 Veux-tu configurer une adresse Kindle ?\n\n"
        "Envoie ton adresse Kindle (ou clique Passer).\n\n"
        "⚠️ Les vieux Kindle ne supportent pas EPUB.\n"
        "Utilise MOBI ou AZW3 pour une meilleure compatibilité."
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(msg_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg_text, reply_markup=keyboard, parse_mode="Markdown")


async def handle_onboarding_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Final step of onboarding: show summary."""
    user_id = update.effective_user.id
    user_prefs = await prefs.get(user_id)

    fmt = user_prefs.get("format", "?")
    email = user_prefs.get("email", "non configuré")
    kindle = user_prefs.get("kindle_email", "non configuré")

    summary_text = (
        "✅ *Configuration terminée !*\n\n"
        f"• Format : `{fmt.upper()}`\n"
        f"• Email : `{email}`\n"
        f"• Kindle : `{kindle}`\n\n"
        "Tu peux maintenant chercher des livres ! "
        "Utilise `/settings` pour modifier tes préférences à tout moment."
    )

    context.user_data.pop("onboarding_step", None)
    context.user_data.pop("waiting_for", None)

    if isinstance(update.callback_query, type(None)):
        # Message context
        await update.message.reply_text(summary_text, parse_mode="Markdown")
    else:
        # Callback context
        await update.callback_query.edit_message_text(summary_text, parse_mode="Markdown")


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command."""
    if not _is_allowed(update):
        return

    user_id = update.effective_user.id
    user_prefs = await prefs.get(user_id)

    fmt = user_prefs.get("format", "epub")
    email = user_prefs.get("email", "non configuré")
    kindle = user_prefs.get("kindle_email", "non configuré")

    text = (
        "⚙️ *Vos préférences :*\n\n"
        f"• Format par défaut : `{fmt.upper()}`\n"
        f"• Email personnel : `{email if email != 'non configuré' else '❌ ' + email}`\n"
        f"• Adresse Kindle : `{kindle if kindle != 'non configuré' else '❌ ' + kindle}`"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Format", callback_data="setfmt_menu")],
        [InlineKeyboardButton("📧 Mon email", callback_data="setemail_prompt")],
        [InlineKeyboardButton("📖 Mon Kindle", callback_data="setkindl_prompt")],
        [InlineKeyboardButton("❌ Supprimer mes données", callback_data="prefs_delete_confirm")],
    ])

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    user_id = update.effective_user.id
    user_prefs = await prefs.get(user_id)

    fmt = user_prefs.get("format", "epub")
    email = user_prefs.get("email", "non configuré")
    kindle = user_prefs.get("kindle_email", "non configuré")

    text = (
        "⚙️ *Vos préférences :*\n\n"
        f"• Format par défaut : `{fmt.upper()}`\n"
        f"• Email personnel : `{email if email != 'non configuré' else '❌ ' + email}`\n"
        f"• Adresse Kindle : `{kindle if kindle != 'non configuré' else '❌ ' + kindle}`"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Format", callback_data="setfmt_menu")],
        [InlineKeyboardButton("📧 Mon email", callback_data="setemail_prompt")],
        [InlineKeyboardButton("📖 Mon Kindle", callback_data="setkindl_prompt")],
        [InlineKeyboardButton("❌ Supprimer mes données", callback_data="prefs_delete_confirm")],
    ])

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def handle_setfmt_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    user_id = update.effective_user.id
    user_prefs = await prefs.get(user_id)
    current_fmt = user_prefs.get("format", "epub")

    buttons = []
    for fmt in ["epub", "pdf", "mobi", "azw3"]:
        if fmt in ALLOWED_FORMATS:
            marker = "✓ " if fmt == current_fmt else ""
            buttons.append([InlineKeyboardButton(f"{marker}{fmt.upper()}", callback_data=f"setfmt_{fmt}")])

    buttons.append([InlineKeyboardButton("⬅️ Retour", callback_data="open_settings")])
    keyboard = InlineKeyboardMarkup(buttons)

    await query.edit_message_text("📚 Quel format préfères-tu ?", reply_markup=keyboard)


async def handle_setfmt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    m = re.match(r"^setfmt_(\w+)$", query.data or "")
    if not m:
        return

    fmt = m.group(1)
    user_id = update.effective_user.id
    await prefs.set(user_id, "format", fmt)

    await query.edit_message_text(f"✅ Format défini à *{fmt.upper()}*", parse_mode="Markdown")
    await asyncio.sleep(1)
    await handle_settings(update, context)


async def handle_setemail_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    context.user_data["waiting_for"] = "email"
    await query.edit_message_text("📧 Envoie-moi ton adresse email :")


async def handle_setkindl_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    context.user_data["waiting_for"] = "kindle_email"
    await query.edit_message_text(
        "📖 Envoie-moi ton adresse Kindle :\n\n"
        "⚠️ *Note :* Les vieux Kindle ne supportent pas EPUB.\n"
        "Utilise *MOBI* ou *AZW3* pour une meilleure compatibilité.",
        parse_mode="Markdown"
    )


async def handle_prefs_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Oui, supprimer", callback_data="prefs_delete_execute")],
        [InlineKeyboardButton("❌ Non, annuler", callback_data="open_settings")],
    ])

    await query.edit_message_text(
        "⚠️ Ceci supprimera toutes tes préférences (format, emails). Continuer ?",
        reply_markup=keyboard,
    )


async def handle_prefs_delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    user_id = update.effective_user.id
    await prefs.delete_user(user_id)
    context.user_data.pop("waiting_for", None)

    await query.edit_message_text("✅ Préférences supprimées. Réutilise /settings pour les reconfigurer.")


async def handle_onb_fmt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Onboarding: set format and continue to email."""
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    m = re.match(r"^onb_fmt_(\w+)$", query.data or "")
    if not m:
        return

    fmt = m.group(1)
    user_id = update.effective_user.id
    await prefs.set(user_id, "format", fmt)

    await query.edit_message_text(f"✅ Format défini à *{fmt.upper()}*", parse_mode="Markdown")
    await asyncio.sleep(0.5)
    await handle_onboarding_email(update, context)


async def handle_onb_skip_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Onboarding: skip email and continue to Kindle."""
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    context.user_data.pop("waiting_for", None)
    await query.edit_message_text("⏭️ Email ignoré.")
    await asyncio.sleep(0.5)
    await handle_onboarding_kindle(update, context)


async def handle_onb_skip_kindle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Onboarding: skip Kindle and show summary."""
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    context.user_data.pop("waiting_for", None)
    await query.edit_message_text("⏭️ Kindle ignoré.")
    await asyncio.sleep(0.5)
    await handle_onboarding_summary(update, context)


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    # Check if waiting for email/Kindle input
    waiting_for = context.user_data.get("waiting_for")
    if waiting_for in ("email", "kindle_email", "onb_email", "onb_kindle"):
        user_input = update.message.text.strip()
        if not user_input:
            await update.message.reply_text("❌ Adresse vide. Essaie à nouveau.")
            return

        # Simple email validation
        if not re.match(r"[^@]+@[^@]+\.[^@]+", user_input):
            await update.message.reply_text("❌ Adresse email invalide. Essaie à nouveau.")
            return

        user_id = update.effective_user.id

        # Handle onboarding flow
        if waiting_for == "onb_email":
            await prefs.set(user_id, "email", user_input)
            context.user_data.pop("waiting_for", None)
            await update.message.reply_text(f"✅ Email configuré : `{user_input}`", parse_mode="Markdown")
            # Continue to next step
            await asyncio.sleep(0.5)
            await handle_onboarding_kindle(update, context)
            return
        elif waiting_for == "onb_kindle":
            await prefs.set(user_id, "kindle_email", user_input)
            context.user_data.pop("waiting_for", None)
            await update.message.reply_text(
                f"✅ Adresse Kindle configurée : `{user_input}`\n\n"
                "💡 *Conseil :* Préfère *MOBI* ou *AZW3* pour envoyer vers Kindle.",
                parse_mode="Markdown"
            )
            # Continue to summary
            await asyncio.sleep(0.5)
            await handle_onboarding_summary(update, context)
            return

        # Handle regular settings flow
        if waiting_for == "email":
            await prefs.set(user_id, "email", user_input)
            context.user_data.pop("waiting_for", None)
            await update.message.reply_text(f"✅ Email configuré : `{user_input}`", parse_mode="Markdown")
        else:  # kindle_email
            await prefs.set(user_id, "kindle_email", user_input)
            context.user_data.pop("waiting_for", None)
            await update.message.reply_text(
                f"✅ Adresse Kindle configurée : `{user_input}`\n\n"
                "💡 *Conseil :* Préfère *MOBI* ou *AZW3* pour envoyer vers Kindle.",
                parse_mode="Markdown"
            )
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

    # Merge: epub/mobi/azw3 first, then other formats — direct before torrents — drop oversized
    def _sort_key(r):
        ext = r.get("ext")
        return (
            0 if ext in ("epub", "mobi", "azw3") else 1,
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

    result = results[idx]
    # Show format menu if multiple formats available
    available_formats = {result.get("ext")}
    if len(ALLOWED_FORMATS) > 1 and available_formats & set(ALLOWED_FORMATS):
        title = result.get("title") or "ce livre"
        fmt_buttons = [
            InlineKeyboardButton("📥 EPUB", callback_data=f"dlfmt_epub_{idx}") if "epub" in ALLOWED_FORMATS else None,
            InlineKeyboardButton("📄 PDF", callback_data=f"dlfmt_pdf_{idx}") if "pdf" in ALLOWED_FORMATS else None,
            InlineKeyboardButton("📱 MOBI", callback_data=f"dlfmt_mobi_{idx}") if "mobi" in ALLOWED_FORMATS else None,
            InlineKeyboardButton("📘 AZW3", callback_data=f"dlfmt_azw3_{idx}") if "azw3" in ALLOWED_FORMATS else None,
        ]
        keyboard = InlineKeyboardMarkup([
            [b for b in fmt_buttons if b],
            [InlineKeyboardButton("⛔ Annuler", callback_data="cancel_dl")],
        ])
        await query.edit_message_text(
            f"📚 « {title[:60]} »\nQuel format veux-tu ?",
            reply_markup=keyboard,
        )
        return

    # Format unique configuré : on télécharge directement
    desired_fmt = ALLOWED_FORMATS[0] if ALLOWED_FORMATS else "epub"
    await _do_download(query, context, idx, desired_fmt=desired_fmt, destination="telegram")


async def handle_download_fmt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    m = re.match(r"^dlfmt_(epub|pdf|mobi|azw3)_(\d+)$", query.data or "")
    if not m:
        return

    fmt, idx = m.group(1), int(m.group(2))

    # Store format choice and check for destination options
    results = context.user_data.get("results", [])
    if idx >= len(results):
        await query.edit_message_text("❌ Résultat expiré, refais une recherche.")
        return

    user_prefs = await prefs.get(update.effective_user.id)
    has_email = bool(user_prefs.get("email"))
    has_kindle = bool(user_prefs.get("kindle_email"))

    # Store format choice
    context.user_data[f"fmt_{idx}"] = fmt

    # If user has configured emails, show destination menu
    if has_email or has_kindle:
        result = results[idx]
        title = result.get("title") or "ce livre"
        dest_buttons = [
            InlineKeyboardButton("📬 Telegram", callback_data=f"dest_telegram_{idx}"),
        ]
        if has_email:
            dest_buttons.append(InlineKeyboardButton("📧 Email", callback_data=f"dest_email_{idx}"))
        if has_kindle:
            dest_buttons.append(InlineKeyboardButton("📖 Kindle", callback_data=f"dest_kindle_{idx}"))

        keyboard = InlineKeyboardMarkup([
            dest_buttons,
            [InlineKeyboardButton("⛔ Annuler", callback_data="cancel_dl")],
        ])
        await query.edit_message_text(
            f"📚 « {title[:50]} »\n\n📬 Où envoyer ?",
            reply_markup=keyboard,
        )
    else:
        # No emails configured, download to Telegram
        await _do_download(query, context, idx, desired_fmt=fmt, destination="telegram")


async def handle_dest_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    m = re.match(r"^dest_telegram_(\d+)$", query.data or "")
    if not m:
        return

    idx = int(m.group(1))
    fmt = context.user_data.get(f"fmt_{idx}", "epub")
    await _do_download(query, context, idx, desired_fmt=fmt, destination="telegram")


async def handle_dest_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    m = re.match(r"^dest_email_(\d+)$", query.data or "")
    if not m:
        return

    idx = int(m.group(1))
    fmt = context.user_data.get(f"fmt_{idx}", "epub")
    await _do_download(query, context, idx, desired_fmt=fmt, destination="email")


async def handle_dest_kindle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not _is_allowed(update):
        return

    m = re.match(r"^dest_kindle_(\d+)$", query.data or "")
    if not m:
        return

    idx = int(m.group(1))
    fmt = context.user_data.get(f"fmt_{idx}", "epub")
    await _do_download(query, context, idx, desired_fmt=fmt, destination="kindle")


async def _do_download(query, context: ContextTypes.DEFAULT_TYPE, idx: int, desired_fmt: str = "epub", destination: str = "telegram", to_pdf: bool = False) -> None:
    results = context.user_data.get("results", [])
    if idx >= len(results):
        await query.edit_message_text("❌ Résultat expiré, refais une recherche.")
        return

    # Convert desired format to to_pdf flag for backwards compatibility
    if not to_pdf:
        to_pdf = desired_fmt == "pdf"

    def _progress_bar(pct: int) -> str:
        filled = pct // 10
        return "▰" * filled + "▱" * (10 - filled)

    async def _try_download(start_idx: int) -> tuple[str, dict] | None | str:
        """Try results from start_idx onwards, return (file_path, result), None, or 'mirrors'."""
        any_mirror_failure = False
        for i in range(start_idx, len(results)):
            result = results[i]
            t = result.get("title") or "livre"
            ext = result.get("ext") or "epub"
            is_torrent = result.get("is_torrent", False)

            # Skip non-EPUB for conversion (unless PDF, then EPUB is OK)
            # We always want to download EPUB for conversion to MOBI/AZW3/PDF
            if desired_fmt in ("mobi", "azw3", "pdf") and ext not in ("epub", "pdf"):
                continue

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
                any_mirror_failure = True
                continue
            except Exception as e:
                logger.warning(f"Result {i} failed ({e}), skipping")
                dots_task.cancel()
                any_mirror_failure = True
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

        return "mirrors" if any_mirror_failure else None

    download_task = asyncio.create_task(_try_download(idx))
    context.user_data["active_dl_task"] = download_task
    try:
        # Use short timeout to allow other handlers (e.g., cancel) to execute
        # while still monitoring the download task
        while not download_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(download_task), timeout=0.5)
            except asyncio.TimeoutError:
                # Timeout is expected — just allows other callbacks to be processed
                continue
        outcome = download_task.result()
    except asyncio.CancelledError:
        return  # message already updated by handle_cancel_download
    finally:
        context.user_data.pop("active_dl_task", None)

    if outcome is None or isinstance(outcome, str):
        if outcome == "mirrors":
            msg_text = (
                "😕 Toutes les sources de téléchargement sont indisponibles pour l'instant.\n"
                "Réessaie dans quelques minutes ou essaie un autre titre."
            )
        else:
            msg_text = "😕 Aucun résultat disponible dans la limite de taille.\nRefais une recherche."
        await query.edit_message_text(msg_text)
        return

    file_path, result = outcome
    title = result.get("title") or "livre"
    ext = result.get("ext") or "epub"

    send_path = file_path
    send_ext = ext
    converted_path = None

    # Convert to desired format if needed
    if ext == "epub" and desired_fmt != "epub":
        try:
            if desired_fmt == "pdf":
                await query.edit_message_text(f"🔄 Conversion en PDF de « {title[:50]} »...")
                converted_path = await converter.epub_to_pdf(file_path)
                send_ext = "pdf"
            elif desired_fmt == "mobi":
                await query.edit_message_text(f"🔄 Conversion en MOBI de « {title[:50]} »...")
                converted_path = await converter.epub_to_mobi(file_path)
                send_ext = "mobi"
            elif desired_fmt == "azw3":
                await query.edit_message_text(f"🔄 Conversion en AZW3 de « {title[:50]} »...")
                converted_path = await converter.epub_to_azw3(file_path)
                send_ext = "azw3"

            if converted_path:
                send_path = converted_path
        except Exception as e:
            logger.warning(f"Conversion to {desired_fmt} failed: {e}")
            await query.edit_message_text(f"⚠️ Conversion {desired_fmt.upper()} échouée, envoi en EPUB à la place.")
            send_path = file_path
            send_ext = ext

    try:
        # VirusTotal scan (skipped if not configured)
        vt_caption = ""
        if virustotal.VT_API_KEY:
            try:
                _vt_frames = [
                    f"🔍 Analyse antivirus de « {title[:45]} » .",
                    f"🔍 Analyse antivirus de « {title[:45]} » ..",
                    f"🔍 Analyse antivirus de « {title[:45]} » ...",
                ]

                async def _animate_vt():
                    i = 0
                    try:
                        while True:
                            try:
                                await query.edit_message_text(_vt_frames[i % len(_vt_frames)])
                            except Exception:
                                pass
                            i += 1
                            await asyncio.sleep(1)
                    except asyncio.CancelledError:
                        pass

                vt_anim = asyncio.create_task(_animate_vt())
                try:
                    stats = await virustotal.scan_file(send_path)
                finally:
                    vt_anim.cancel()
                if stats:
                    malicious = stats.get("malicious", 0)
                    suspicious = stats.get("suspicious", 0)
                    if malicious > 0:
                        await query.edit_message_text(
                            f"🚨 Fichier bloqué — détecté comme malveillant par {malicious} scanner(s) VirusTotal."
                        )
                        return
                    elif suspicious > 0:
                        vt_caption = f"\n⚠️ Signalé comme suspect par {suspicious} scanner(s) VirusTotal"
            except Exception as e:
                logger.warning(f"VirusTotal scan failed: {e}")
                vt_caption = "\n⚠️ Analyse VirusTotal indisponible"

        safe_title = re.sub(r'[^\w\s\-]', '', title).strip()[:60] or "livre"
        filename = f"{safe_title}.{send_ext}"

        if destination == "telegram":
            await query.edit_message_text(f"📤 Envoi de « {title} »...")
            with open(send_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename=filename,
                    caption=f"📖 {title}{vt_caption}",
                )
            await query.edit_message_text(f"✅ Envoyé ! Bonne lecture 📖")

        elif destination == "email":
            user_id = query.from_user.id
            user_prefs = await prefs.get(user_id)
            email_addr = user_prefs.get("email")
            if not email_addr:
                await query.edit_message_text("❌ Adresse email non configurée. Utilise /settings")
                return
            try:
                await query.edit_message_text(f"📧 Envoi par email à {email_addr}...")
                await mailer.send_file(send_path, filename, email_addr, kindle=False)
                await query.edit_message_text(f"✅ Email envoyé à {email_addr} 📧")
            except Exception as e:
                logger.warning(f"Email send failed: {e}")
                await query.edit_message_text("❌ Envoi email échoué. Vérifie la configuration SMTP dans /settings.")

        elif destination == "kindle":
            user_id = query.from_user.id
            user_prefs = await prefs.get(user_id)
            kindle_email = user_prefs.get("kindle_email")
            if not kindle_email:
                await query.edit_message_text("❌ Adresse Kindle non configurée. Utilise /settings")
                return
            try:
                await query.edit_message_text(f"📖 Envoi vers Kindle ({kindle_email})...")
                await mailer.send_file(send_path, filename, kindle_email, kindle=True)
                await query.edit_message_text(f"✅ Envoyé vers votre Kindle ! 📖")
            except Exception as e:
                logger.warning(f"Kindle send failed: {e}")
                await query.edit_message_text("❌ Envoi Kindle échoué. Vérifie l'adresse Kindle et la config SMTP dans /settings.")
    finally:
        # Clean up temp files (not watcher paths — owned by the download client)
        for path in (file_path, converted_path):
            if path and path.startswith(tempfile.gettempdir()):
                try:
                    os.remove(path)
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
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)
    )
    app.add_handler(CallbackQueryHandler(handle_download, pattern=r"^dl_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_download_fmt, pattern=r"^dlfmt_(epub|pdf|mobi|azw3)_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_dest_telegram, pattern=r"^dest_telegram_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_dest_email, pattern=r"^dest_email_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_dest_kindle, pattern=r"^dest_kindle_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_confirm_non_epub, pattern=r"^confirm_non_epub$"))
    app.add_handler(CallbackQueryHandler(handle_cancel_search, pattern=r"^cancel_search$"))
    app.add_handler(CallbackQueryHandler(handle_cancel_download, pattern=r"^cancel_dl$"))
    app.add_handler(CallbackQueryHandler(handle_settings, pattern=r"^open_settings$"))
    app.add_handler(CallbackQueryHandler(handle_setfmt_menu, pattern=r"^setfmt_menu$"))
    app.add_handler(CallbackQueryHandler(handle_setfmt, pattern=r"^setfmt_\w+$"))
    app.add_handler(CallbackQueryHandler(handle_setemail_prompt, pattern=r"^setemail_prompt$"))
    app.add_handler(CallbackQueryHandler(handle_setkindl_prompt, pattern=r"^setkindl_prompt$"))
    app.add_handler(CallbackQueryHandler(handle_prefs_delete_confirm, pattern=r"^prefs_delete_confirm$"))
    app.add_handler(CallbackQueryHandler(handle_prefs_delete_execute, pattern=r"^prefs_delete_execute$"))
    app.add_handler(CallbackQueryHandler(handle_onb_fmt, pattern=r"^onb_fmt_\w+$"))
    app.add_handler(CallbackQueryHandler(handle_onb_skip_email, pattern=r"^onb_skip_email$"))
    app.add_handler(CallbackQueryHandler(handle_onb_skip_kindle, pattern=r"^onb_skip_kindle$"))

    if GITHUB_REPO:
        app.job_queue.run_repeating(check_for_updates, interval=86400, first=30)
        logger.info(f"Update checks enabled for {GITHUB_REPO} (every 24h)")

    _cleanup_orphaned_temp_files()
    if os.environ.get("ANNA_ARCHIVE_URL", "").startswith("http://"):
        logger.warning("ANNA_ARCHIVE_URL uses unencrypted HTTP — HTTPS is recommended")

    logger.info(f"--- maman-books v{VERSION} ---")
    logger.info(f"  Anna's Archive : {'✓ ' + os.environ.get('ANNA_ARCHIVE_URL', '') if os.environ.get('ANNA_ARCHIVE_URL') else '✗ désactivée'}")
    logger.info(f"  Prowlarr       : {'✓ ' + os.environ.get('PROWLARR_URL', '') if os.environ.get('PROWLARR_URL') else '✗ désactivé'}")
    logger.info(f"  Formats        : {', '.join(ALLOWED_FORMATS)}")
    logger.info(f"  VirusTotal     : {'✓ activé' if virustotal.VT_API_KEY else '✗ désactivé'}")
    logger.info(f"  Calibre        : {'✓ ebook-convert trouvé' if converter.ebook_convert_available() else '✗ absent — fallback PyMuPDF pour MOBI/AZW3'}")
    logger.info(f"  Email / Kindle : {'✓ activé' if mailer.is_configured() else '✗ désactivé'}")
    logger.info(f"  Mises à jour   : {'✓ ' + GITHUB_REPO if GITHUB_REPO else '✗ désactivées'}")
    logger.info(f"  Limite fichier : {MAX_FILE_SIZE // 1024 // 1024} MB{'  [local Bot API]' if LOCAL_API_SERVER else ''}")
    logger.info(f"  Utilisateurs   : {len(ALLOWED_USER_IDS)} autorisé(s)")
    logger.info("Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
