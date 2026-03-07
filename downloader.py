import httpx
import ipaddress
import os
import re
import tempfile
import logging
import time
from urllib.parse import urlparse
import anna_archive
import prowlarr
import watcher

logger = logging.getLogger(__name__)

VALID_CONTENT_TYPES = {
    "application/epub+zip",
    "application/pdf",
    "application/x-mobipocket-ebook",
    "application/octet-stream",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _is_safe_url(url: str) -> bool:
    """Return False if the URL targets an internal/private resource (SSRF protection)."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = p.hostname or ""
        if not host or host.lower() == "localhost":
            return False
        try:
            ip = ipaddress.ip_address(host)
            return not (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved)
        except ValueError:
            return True
    except Exception:
        return False


def _sanitize_ext(ext: str) -> str:
    cleaned = re.sub(r'[^a-z0-9]', '', (ext or '').lower())[:10]
    return cleaned or 'epub'


async def _check_redirect(response: httpx.Response) -> None:
    """httpx hook: block redirects to internal IPs (SSRF protection on redirects)."""
    if response.is_redirect:
        location = str(response.headers.get("location", ""))
        if location and not _is_safe_url(location):
            raise ValueError("Redirect blocked (SSRF)")


async def download_result(result: dict, progress_callback=None, max_bytes: int = 0) -> str:
    """
    Download a search result to a temp file and return its path.
    Handles Anna's Archive, Prowlarr direct, and Prowlarr torrent.
    """
    source = result.get("source")
    ext = _sanitize_ext(result.get("ext", "epub"))

    if source == "anna":
        return await anna_archive.download(result["md5"], ext, progress_callback, max_bytes=max_bytes)

    if source == "prowlarr":
        if result.get("is_torrent"):
            return await _download_torrent(result)
        else:
            return await _download_direct(result["download_url"], ext, progress_callback, max_bytes=max_bytes)

    raise ValueError(f"Unknown source: {source!r}")


async def _download_direct(url: str, ext: str, progress_callback=None, max_bytes: int = 0) -> str:
    """Stream a direct download URL to a temp file."""
    if not _is_safe_url(url):
        raise ValueError("URL rejected (SSRF protection)")
    ext = _sanitize_ext(ext)
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=60, follow_redirects=True,
        event_hooks={"response": [_check_redirect]},
    ) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "").split(";")[0].strip()
            if ctype and ctype not in VALID_CONTENT_TYPES:
                raise RuntimeError(f"Unexpected content-type: {ctype!r}")
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            last_report = 0.0
            last_pct = -1
            suffix = f".{ext}" if ext else ".epub"
            path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="maman_") as f:
                    path = f.name
                    async for chunk in resp.aiter_bytes(65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if max_bytes and downloaded > max_bytes:
                            raise RuntimeError(f"File too large (>{max_bytes // 1024 // 1024} MB)")
                        if progress_callback:
                            now = time.monotonic()
                            pct = int(downloaded / total * 100) if total else 0
                            if now - last_report >= 2.0 and pct != last_pct:
                                last_report = now
                                last_pct = pct
                                try:
                                    await progress_callback(downloaded, total)
                                except Exception:
                                    pass
            except Exception:
                if path:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                raise
            return path


async def _download_torrent(result: dict) -> str:
    """Grab via Prowlarr and watch download folder for the resulting file."""
    download_path = os.environ.get("BOOKS_DOWNLOAD_PATH", "/downloads/books")
    timeout_minutes = int(os.environ.get("DOWNLOAD_TIMEOUT_MINUTES", "15"))

    await prowlarr.grab(result["indexer_id"], result["guid"])
    path = await watcher.wait_for_file(
        result["title"], download_path, timeout_minutes
    )
    return path
