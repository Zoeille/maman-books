"""Persistent user preferences storage (JSON-based, per-user)."""

import asyncio
import json
import os
import tempfile
from typing import Any

PREFS_FILE = os.environ.get("USER_PREFS_FILE", "user_prefs.json")
_lock = asyncio.Lock()


async def get(user_id: int) -> dict:
    """Get all preferences for a user. Returns {} if user not found."""
    async with _lock:
        if not os.path.exists(PREFS_FILE):
            return {}
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(str(user_id), {})
        except Exception:
            return {}


async def get_all(user_id: int) -> dict:
    """Alias for get()."""
    return await get(user_id)


async def set(user_id: int, key: str, value: Any) -> None:
    """Set a preference key for a user. Atomic write via temp file."""
    async with _lock:
        data = {}
        if os.path.exists(PREFS_FILE):
            try:
                with open(PREFS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

        user_key = str(user_id)
        if user_key not in data:
            data[user_key] = {}

        data[user_key][key] = value

        # Atomic write via temp file + os.replace()
        fd, temp_path = tempfile.mkstemp(text=True, suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, PREFS_FILE)
        except Exception:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise


async def delete_user(user_id: int) -> None:
    """Delete all preferences for a user."""
    async with _lock:
        if not os.path.exists(PREFS_FILE):
            return
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        user_key = str(user_id)
        if user_key in data:
            del data[user_key]

            # Atomic write
            fd, temp_path = tempfile.mkstemp(text=True, suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(temp_path, PREFS_FILE)
            except Exception:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                raise
