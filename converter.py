import asyncio
import logging
import os
import shutil
import subprocess
import tempfile

import fitz  # pymupdf

logger = logging.getLogger(__name__)


def ebook_convert_available() -> bool:
    """Return True if Calibre's ebook-convert is available in PATH."""
    return shutil.which("ebook-convert") is not None


def _convert_sync(epub_path: str) -> str:
    """Blocking epub→PDF conversion using PyMuPDF."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="maman_") as f:
        pdf_path = f.name
    try:
        doc = fitz.open(epub_path)
        doc.save(pdf_path)
        doc.close()
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < 1024:
            raise RuntimeError("PyMuPDF produced an empty or missing PDF")
        return pdf_path
    except Exception:
        try:
            os.remove(pdf_path)
        except Exception:
            pass
        raise


async def epub_to_pdf(epub_path: str) -> str:
    """Convert an epub file to PDF. Returns path to PDF temp file."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _convert_sync, epub_path)


def _convert_to_format_sync(epub_path: str, fmt: str) -> str:
    """Blocking epub→MOBI/AZW3 conversion. Uses Calibre if available, else PyMuPDF."""
    suffix = f".{fmt}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="maman_") as f:
        output_path = f.name

    try:
        if ebook_convert_available():
            _convert_with_calibre(epub_path, output_path)
        else:
            logger.warning(
                f"ebook-convert not found — falling back to PyMuPDF for {fmt.upper()} "
                "(install Calibre for accurate conversion)"
            )
            doc = fitz.open(epub_path)
            doc.save(output_path)
            doc.close()

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            raise RuntimeError(f"Conversion produced an empty or missing {fmt.upper()} file")
        return output_path
    except Exception:
        try:
            os.remove(output_path)
        except Exception:
            pass
        raise


def _convert_with_calibre(input_path: str, output_path: str) -> None:
    """Convert using Calibre's ebook-convert CLI (blocking)."""
    cmd = shutil.which("ebook-convert")
    result = subprocess.run(
        [cmd, input_path, output_path],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ebook-convert failed: {result.stderr[:300]}")


async def epub_to_mobi(epub_path: str) -> str:
    """Convert an epub file to MOBI. Returns path to MOBI temp file."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _convert_to_format_sync, epub_path, "mobi")


async def epub_to_azw3(epub_path: str) -> str:
    """Convert an epub file to AZW3. Returns path to AZW3 temp file."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _convert_to_format_sync, epub_path, "azw3")
