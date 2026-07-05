"""字幕记录：本地 JSON 持久化（单用户 demo）。"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT


def _records_dir() -> Path:
    d = BACKEND_ROOT / "data" / "subtitles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _record_path(record_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", record_id).strip("._-")[:180]
    if not safe:
        raise ValueError("invalid record id")
    return _records_dir() / f"{safe}.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_record(payload: dict[str, Any]) -> dict[str, Any]:
    record_id = str(payload.get("id") or "").strip() or uuid.uuid4().hex[:12]
    now = _now_iso()
    record = {
        "id": record_id,
        "source_url": payload.get("source_url") or "",
        "bvid": payload.get("bvid") or "",
        "aid": int(payload.get("aid") or 0),
        "cid": int(payload.get("cid") or 0),
        "title": payload.get("title") or "",
        "page": int(payload.get("page") or 1),
        "page_title": payload.get("page_title") or "",
        "selected_track": payload.get("selected_track"),
        "lines": payload.get("lines") or [],
        "text": payload.get("text") or "",
        "line_count": len(payload.get("lines") or []),
        "created_at": payload.get("created_at") or now,
        "updated_at": now,
    }
    _record_path(record_id).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def list_records() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in _records_dir().glob("*.json"):
        rec = _read_file(path)
        if rec:
            items.append(_summary(rec))
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return items


def get_record(record_id: str) -> dict[str, Any] | None:
    return _read_file(_record_path(record_id))


def delete_record(record_id: str) -> bool:
    path = _record_path(record_id)
    if not path.is_file():
        return False
    path.unlink()
    return True


def _read_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    raw.setdefault("id", path.stem)
    raw["line_count"] = len(raw.get("lines") or [])
    return raw


def _summary(rec: dict[str, Any]) -> dict[str, Any]:
    track = rec.get("selected_track") or {}
    return {
        "id": rec.get("id") or "",
        "bvid": rec.get("bvid") or "",
        "title": rec.get("title") or "",
        "page": rec.get("page") or 1,
        "page_title": rec.get("page_title") or "",
        "line_count": rec.get("line_count") or 0,
        "lan_doc": track.get("lan_doc") or track.get("lan") or "",
        "source_url": rec.get("source_url") or "",
        "created_at": rec.get("created_at") or "",
        "updated_at": rec.get("updated_at") or "",
    }


def _self_check() -> None:
    rid = f"test_{uuid.uuid4().hex[:6]}"
    saved = save_record(
        {
            "id": rid,
            "source_url": "https://example.com",
            "bvid": "BVtest",
            "title": "测试",
            "lines": [{"from": 0, "to": 1, "content": "hi"}],
            "text": "[00:00.00] hi",
        }
    )
    assert get_record(rid)["title"] == "测试"
    assert any(x["id"] == rid for x in list_records())
    assert delete_record(rid)


if __name__ == "__main__":
    _self_check()
    print("subtitle_store self-check ok")
