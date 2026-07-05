"""应用设置：backend/data/settings.json（单用户 demo）。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT

_SETTINGS_PATH = BACKEND_ROOT / "data" / "settings.json"

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


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


def get_openai_api_key() -> str | None:
    """优先 settings.json，fallback .env。"""
    from_file = (load_settings().get("openai_api_key") or "").strip()
    if from_file:
        return from_file
    from_env = os.getenv("OPENAI_API_KEY", "").strip()
    return from_env or None


def get_openai_base_url() -> str:
    """优先 settings.json，fallback .env，再默认 OpenAI 端点。"""
    from_file = (load_settings().get("openai_base_url") or "").strip()
    if from_file:
        return from_file
    from_env = os.getenv("OPENAI_BASE_URL", "").strip()
    return from_env or DEFAULT_OPENAI_BASE_URL


def get_openai_model() -> str:
    """优先 settings.json，fallback .env，再默认模型。"""
    from_file = (load_settings().get("openai_model") or "").strip()
    if from_file:
        return from_file
    from_env = os.getenv("OPENAI_MODEL", "").strip()
    return from_env or DEFAULT_OPENAI_MODEL


def public_settings() -> dict[str, Any]:
    bili = get_bilibili_sessdata() or ""
    xhs = get_xiaohongshu_cookie() or ""
    openai_key = get_openai_api_key() or ""
    return {
        "bilibili_sessdata_configured": bool(bili),
        "bilibili_sessdata_masked": mask_secret(bili),
        "xiaohongshu_cookie_configured": bool(xhs),
        "xiaohongshu_cookie_masked": mask_secret(xhs),
        "openai_api_key_configured": bool(openai_key),
        "openai_api_key_masked": mask_secret(openai_key),
        "openai_base_url": get_openai_base_url(),
        "openai_model": get_openai_model(),
    }


def _self_check() -> None:
    pub = public_settings()
    assert pub["openai_api_key_configured"] or bool(get_openai_api_key())
    assert pub["openai_base_url"]
    assert pub["openai_model"]
    assert "****" in pub["openai_api_key_masked"] or not pub["openai_api_key_configured"]
    assert pub["openai_base_url"] == get_openai_base_url()
    assert pub["openai_model"] == get_openai_model()


if __name__ == "__main__":
    _self_check()
    pub = public_settings()
    print("settings_store self-check ok")
    print(f"  openai_configured={pub['openai_api_key_configured']}")
    print(f"  openai_base_url={pub['openai_base_url']}")
    print(f"  openai_model={pub['openai_model']}")
    print(f"  openai_key_masked={pub['openai_api_key_masked']}")
