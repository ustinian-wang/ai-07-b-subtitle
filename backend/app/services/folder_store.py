"""字幕库文件夹：本地 JSON 树形目录（单用户 demo）。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT

_FOLDERS_PATH = BACKEND_ROOT / "data" / "folders.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    _FOLDERS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_raw() -> list[dict[str, Any]]:
    _ensure_dir()
    if not _FOLDERS_PATH.is_file():
        return []
    try:
        raw = json.loads(_FOLDERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict) and x.get("id")]


def _save_raw(items: list[dict[str, Any]]) -> None:
    _ensure_dir()
    _FOLDERS_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def list_folders() -> list[dict[str, Any]]:
    items = sorted(_load_raw(), key=lambda x: (x.get("name") or "").lower())
    return [_public(x) for x in items]


def get_folder(folder_id: str) -> dict[str, Any] | None:
    for item in _load_raw():
        if item.get("id") == folder_id:
            return _public(item)
    return None


def _find_raw(folder_id: str) -> dict[str, Any] | None:
    for item in _load_raw():
        if item.get("id") == folder_id:
            return item
    return None


def _descendant_ids(folder_id: str, items: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    stack = [folder_id]
    while stack:
        cur = stack.pop()
        for item in items:
            pid = item.get("parent_id")
            if pid == cur and item.get("id"):
                fid = item["id"]
                if fid not in out:
                    out.add(fid)
                    stack.append(fid)
    return out


def create_folder(name: str, parent_id: str | None = None) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("文件夹名称不能为空")
    items = _load_raw()
    if parent_id and not _find_raw(parent_id):
        raise ValueError("父文件夹不存在")
    folder_id = uuid.uuid4().hex[:10]
    now = _now_iso()
    item = {
        "id": folder_id,
        "name": name,
        "parent_id": parent_id,
        "created_at": now,
        "updated_at": now,
    }
    items.append(item)
    _save_raw(items)
    return _public(item)


_UNSET = object()


def update_folder(
    folder_id: str,
    *,
    name: str | None = None,
    parent_id: str | None | object = _UNSET,
) -> dict[str, Any]:
    items = _load_raw()
    item = _find_raw(folder_id)
    if not item:
        raise ValueError("文件夹不存在")

    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("文件夹名称不能为空")
        item["name"] = name

    if parent_id is not _UNSET:
        if parent_id == folder_id:
            raise ValueError("不能移动到自身")
        if parent_id and parent_id not in {x.get("id") for x in items}:
            raise ValueError("目标父文件夹不存在")
        if parent_id and parent_id in _descendant_ids(folder_id, items):
            raise ValueError("不能移动到子文件夹")
        item["parent_id"] = parent_id

    item["updated_at"] = _now_iso()
    _save_raw(items)
    return _public(item)


def delete_folder(folder_id: str) -> dict[str, Any]:
    items = _load_raw()
    item = _find_raw(folder_id)
    if not item:
        raise ValueError("文件夹不存在")
    parent_id = item.get("parent_id")
    child_ids = _descendant_ids(folder_id, items)
    removed = {folder_id, *child_ids}
    remaining = [x for x in items if x.get("id") not in removed]
    # ponytail: 子文件夹挂到被删文件夹的 parent，记录由 subtitle_store 单独处理
    for x in remaining:
        if x.get("parent_id") in removed:
            x["parent_id"] = parent_id
            x["updated_at"] = _now_iso()
    _save_raw(remaining)
    return {"deleted_id": folder_id, "moved_children_to": parent_id, "removed_descendants": list(child_ids)}


def _public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id") or "",
        "name": item.get("name") or "",
        "parent_id": item.get("parent_id"),
        "created_at": item.get("created_at") or "",
        "updated_at": item.get("updated_at") or "",
    }


def descendant_folder_ids(folder_id: str) -> set[str]:
    return _descendant_ids(folder_id, _load_raw())


def load_all_folders() -> list[dict[str, Any]]:
    return _load_raw()


def _self_check() -> None:
    f1 = create_folder("测试A")
    f2 = create_folder("测试B", parent_id=f1["id"])
    assert get_folder(f2["id"])["parent_id"] == f1["id"]
    updated = update_folder(f1["id"], name="测试A改")
    assert updated["name"] == "测试A改"
    delete_folder(f1["id"])
    assert get_folder(f1["id"]) is None
    assert get_folder(f2["id"]) is None


if __name__ == "__main__":
    _self_check()
    print("folder_store self-check ok")
