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


def make_dedupe_key(bvid: str, page: int, lan: str) -> str:
    safe_bvid = re.sub(r"[^a-zA-Z0-9._-]+", "_", (bvid or "").strip())[:80]
    safe_lan = re.sub(r"[^a-zA-Z0-9._-]+", "_", (lan or "unknown").strip().lower())[:40]
    return f"{safe_bvid}_p{int(page or 1)}_{safe_lan}"


def _lan_from_record(rec: dict[str, Any]) -> str:
    track = rec.get("selected_track") or {}
    return (track.get("lan") or track.get("lan_doc") or "").strip()


def find_by_dedupe_key(bvid: str, page: int, lan: str) -> dict[str, Any] | None:
    key = make_dedupe_key(bvid, page, lan)
    for path in _records_dir().glob("*.json"):
        rec = _read_file(path)
        if rec and (rec.get("dedupe_key") or make_dedupe_key(
            rec.get("bvid") or "", int(rec.get("page") or 1), _lan_from_record(rec)
        )) == key:
            return rec
    return None


def find_by_bvid_page(bvid: str, page: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in _records_dir().glob("*.json"):
        rec = _read_file(path)
        if rec and (rec.get("bvid") or "") == bvid and int(rec.get("page") or 1) == int(page or 1):
            items.append(rec)
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return items


def _pick_existing_record(records: list[dict[str, Any]], lang: str | None) -> dict[str, Any] | None:
    if not records:
        return None
    if lang:
        found = find_by_dedupe_key(records[0].get("bvid") or "", int(records[0].get("page") or 1), lang)
        return found
    for prefer in ("zh-cn", "zh", "ai-zh", "ai_zh"):
        for rec in records:
            if _lan_from_record(rec).lower() == prefer:
                return rec
    return records[0]


def upsert_record(payload: dict[str, Any]) -> dict[str, Any]:
    bvid = payload.get("bvid") or ""
    page = int(payload.get("page") or 1)
    track = payload.get("selected_track") or {}
    lan = (track.get("lan") or track.get("lan_doc") or "").strip()
    existing = find_by_dedupe_key(bvid, page, lan)
    if existing:
        payload = {**payload, "id": existing["id"], "created_at": existing.get("created_at")}
    return save_record(payload)


def save_record(payload: dict[str, Any]) -> dict[str, Any]:
    record_id = str(payload.get("id") or "").strip() or uuid.uuid4().hex[:12]
    now = _now_iso()
    track = payload.get("selected_track") or {}
    lan = (track.get("lan") or track.get("lan_doc") or "").strip()
    record = {
        "id": record_id,
        "dedupe_key": make_dedupe_key(payload.get("bvid") or "", int(payload.get("page") or 1), lan),
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


def delete_records(record_ids: list[str]) -> dict[str, list[str]]:
    deleted: list[str] = []
    failed: list[str] = []
    for rid in record_ids:
        if delete_record(rid):
            deleted.append(rid)
        else:
            failed.append(rid)
    return {"deleted": deleted, "failed": failed}


EXPORT_SEPARATOR = "\n\n---\n\n"


def export_records(record_ids: list[str], fmt: str = "txt") -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    missing: list[str] = []
    for rid in record_ids:
        rec = get_record(rid)
        if rec:
            records.append(rec)
        else:
            missing.append(rid)
    if fmt == "json":
        content = json.dumps(records, ensure_ascii=False, indent=2)
        filename = "subtitles_export.json"
    else:
        parts = [rec.get("text") or "" for rec in records]
        content = EXPORT_SEPARATOR.join(parts)
        filename = "subtitles_export.txt"
    return {
        "format": fmt,
        "content": content,
        "filename": filename,
        "count": len(records),
        "missing": missing,
    }


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
            "selected_track": {"lan": "zh-CN", "lan_doc": "中文"},
            "lines": [{"from": 0, "to": 1, "content": "hi"}],
            "text": "[00:00.00] hi",
        }
    )
    assert get_record(rid)["title"] == "测试"
    assert saved["dedupe_key"] == make_dedupe_key("BVtest", 1, "zh-CN")
    assert find_by_dedupe_key("BVtest", 1, "zh-CN")["id"] == rid
    assert any(x["id"] == rid for x in list_records())

    rid2 = upsert_record(
        {
            "source_url": "https://example.com/2",
            "bvid": "BVtest",
            "title": "测试更新",
            "page": 1,
            "selected_track": {"lan": "zh-CN", "lan_doc": "中文"},
            "lines": [{"from": 0, "to": 2, "content": "updated"}],
            "text": "[00:00.00] updated",
        }
    )
    assert rid2["id"] == rid
    assert get_record(rid)["title"] == "测试更新"

    exp = export_records([rid], fmt="txt")
    assert "updated" in exp["content"]
    batch = delete_records([rid])
    assert rid in batch["deleted"]


if __name__ == "__main__":
    _self_check()
    print("subtitle_store self-check ok")
