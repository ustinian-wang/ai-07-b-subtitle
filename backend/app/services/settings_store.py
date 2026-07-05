"""应用设置：backend/data/settings.json（单用户 demo）。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT

_SETTINGS_PATH = BACKEND_ROOT / "data" / "settings.json"


def _ensure_dir() -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict[str, Any]:
    _ensure_dir()
    if not _SETTINGS_PATH.is_file():
        return {}
    try:
        raw = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError, UnicodeError):
        return {}


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    _ensure_dir()
    _SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def patch_settings(updates: dict[str, Any]) -> dict[str, Any]:
    cur = load_settings()
    cur.update(updates)
    return save_settings(cur)


def mask_secret(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return "****"
    return f"{text[:4]}****{text[-4:]}"


def get_bilibili_sessdata() -> str | None:
    """优先 settings.json，fallback .env。"""
    from_file = (load_settings().get("bilibili_sessdata") or "").strip()
    if from_file:
        return from_file
    from_env = os.getenv("BILIBILI_SESSDATA", "").strip()
    return from_env or None


def get_xiaohongshu_cookie() -> str | None:
    """优先 settings.json，fallback .env。"""
    from_file = (load_settings().get("xiaohongshu_cookie") or "").strip()
    if from_file:
        return from_file
    from_env = os.getenv("XIAOHONGSHU_COOKIE", "").strip()
    return from_env or None


def public_settings() -> dict[str, Any]:
    bili = get_bilibili_sessdata() or ""
    xhs = get_xiaohongshu_cookie() or ""
    return {
        "bilibili_sessdata_configured": bool(bili),
        "bilibili_sessdata_masked": mask_secret(bili),
        "xiaohongshu_cookie_configured": bool(xhs),
        "xiaohongshu_cookie_masked": mask_secret(xhs),
    }
