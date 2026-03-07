#!/usr/bin/env python3
"""Mini serveur web Flask pour recherche + téléchargement de livres."""
import asyncio
import logging
import os
import re
import secrets
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file, send_from_directory
from werkzeug.exceptions import BadRequest, NotFound

load_dotenv()

import anna_archive
import prowlarr
import downloader

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# Configuration
MAX_RESULTS = 10
MAX_QUERY_LENGTH = 200
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
CACHE_TTL_SECONDS = 3600

# Stockage temporaire des résultats de recherche (en mémoire)
# Format: {session_id: {"results": [...], "timestamp": float}}
search_cache = {}


def _fmt_size(size_bytes: int) -> str:
    if not size_bytes:
        return "?"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} Ko"
    return f"{size_bytes / 1024 / 1024:.1f} Mo"


def _sanitize_filename(title: str) -> str:
    return re.sub(r'[^\w\s\-\_\.\,]', '', title or 'livre')[:100]


async def _safe_search(search_func, query: str, source_name: str):
    """Execute search with error handling."""
    try:
        return await search_func(query)
    except Exception as e:
        logger.error(f"{source_name} search failed: {e}")
        return []


def _cleanup_expired_cache() -> None:
    now = time.time()
    expired_keys = [sid for sid, data in search_cache.items() if now - data.get("timestamp", 0) > CACHE_TTL_SECONDS]
    for sid in expired_keys:
        del search_cache[sid]


@app.route('/')
def index():
    """Serve la page HTML principale."""
    web_dir = Path(__file__).parent / 'web'
    return send_from_directory(web_dir, 'index.html')


@app.route('/rechercher', methods=['POST'])
def rechercher():
    """
    Endpoint de recherche.
    Attend un JSON: {"titre": "nom du livre"}
    Retourne: {"session_id": "...", "results": [...]}
    """
    data = request.get_json() or {}
    query = (data.get('titre') or '').strip()
    if not query:
        raise BadRequest("Le champ 'titre' est requis")
    if len(query) > MAX_QUERY_LENGTH:
        raise BadRequest(f"Requête trop longue (max {MAX_QUERY_LENGTH} caractères)")

    logger.info(f"🔍 Recherche: {query!r}")

    async def do_search():
        return await asyncio.gather(
            _safe_search(anna_archive.search, query, "Anna's Archive"),
            _safe_search(prowlarr.search, query, "Prowlarr"),
        )

    aa_results, pr_results = asyncio.run(do_search())

    logger.info(f"Anna's Archive: {len(aa_results)} résultats")
    logger.info(f"Prowlarr: {len(pr_results)} résultats")

    all_results = aa_results + pr_results
    all_results.sort(key=lambda r: (
        0 if r.get("ext") == "epub" else 1,
        0 if not r.get("is_torrent") else 1,
    ))

    results = []
    seen_titles: set[str] = set()
    for result in all_results:
        if result.get("size_bytes", 0) > MAX_FILE_SIZE:
            continue
        norm = re.sub(r"[^\w]", "", (result.get("title") or "")).lower()[:35]
        if norm and norm in seen_titles:
            continue
        if norm:
            seen_titles.add(norm)
        results.append(result)
        if len(results) >= MAX_RESULTS:
            break

    logger.info(f"✅ {len(results)} résultats après fusion et déduplication")

    session_id = secrets.token_urlsafe(16)
    search_cache[session_id] = {"results": results, "timestamp": time.time()}
    _cleanup_expired_cache()

    payload = []
    for i, result in enumerate(results):
        payload.append({
            "id": f"{session_id}_{i}",
            "title": result.get("title", "?"),
            "author": result.get("author", ""),
            "ext": result.get("ext", "epub"),
            "size": _fmt_size(result.get("size_bytes", 0)),
            "is_torrent": result.get("is_torrent", False),
        })

    return jsonify({"session_id": session_id, "results": payload})


@app.route('/telecharger/<result_id>')
def telecharger(result_id):
    """
    Endpoint de téléchargement.
    result_id format: {session_id}_{index}
    """
    try:
        session_id, index_str = result_id.rsplit('_', 1)
        index = int(index_str)
    except (ValueError, AttributeError):
        raise BadRequest("ID de résultat invalide")

    session_data = search_cache.get(session_id)
    if not session_data:
        raise NotFound("Session expirée ou introuvable. Refaites une recherche.")

    results = session_data.get("results", [])
    if index < 0 or index >= len(results):
        raise NotFound("Résultat introuvable")

    result = results[index]
    logger.info(f"📥 Téléchargement: {result.get('title', '?')} ({result.get('ext', '?')})")
    
    # Télécharge le fichier
    try:
        file_path = asyncio.run(downloader.download_result(
            result,
            progress_callback=None,
            max_bytes=MAX_FILE_SIZE
        ))
    except Exception as e:
        logger.error(f"Erreur de téléchargement: {e}")
        raise BadRequest(f"Échec du téléchargement: {str(e)}")
    
    # Détermine le nom de fichier
    safe_title = _sanitize_filename(result.get("title", "livre"))
    ext = result.get("ext", "epub")
    filename = f"{safe_title}.{ext}"
    
    logger.info(f"✅ Envoi du fichier: {filename}")
    
    # Envoie le fichier avec suppression automatique après envoi
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/octet-stream'
    )


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


def main():
    """Lance le serveur web."""
    host = os.environ.get('WEB_HOST', '0.0.0.0')
    port = int(os.environ.get('WEB_PORT', '5050'))
    debug = os.environ.get('WEB_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"🚀 Démarrage du serveur sur {host}:{port}")
    logger.info(f"📚 Anna's Archive: {os.environ.get('ANNA_ARCHIVE_URL', 'non configuré')}")
    logger.info(f"📚 Prowlarr: {os.environ.get('PROWLARR_URL', 'non configuré')}")
    
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()
