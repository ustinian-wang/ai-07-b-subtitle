"""内容库文件夹：本地 JSON 树形目录（单用户 demo）。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT

_FOLDERS_PATH = BACKEND_ROOT / "data" / "folders.json"

UNCATEGORIZED_FOLDER_ID = "__uncategorized__"
UNCATEGORIZED_FOLDER_NAME = "未分类"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    _FOLDERS_PATH.parent.mkdir(parents=True, exist_ok=True)


def is_system_folder(folder_id: str | None) -> bool:
    return folder_id == UNCATEGORIZED_FOLDER_ID


def is_uncategorized_folder_id(folder_id: str | None) -> bool:
    if folder_id is None or folder_id == "":
        return True
    return folder_id == UNCATEGORIZED_FOLDER_ID


def _read_raw_file() -> list[dict[str, Any]]:
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


def _patch_system_folder(items: list[dict[str, Any]]) -> bool:
    """确保「未分类」系统文件夹存在且字段正确。"""
    changed = False
    sys = next((x for x in items if x.get("id") == UNCATEGORIZED_FOLDER_ID), None)
    now = _now_iso()
    if sys:
        if not sys.get("system"):
            sys["system"] = True
            changed = True
        if sys.get("name") != UNCATEGORIZED_FOLDER_NAME:
            sys["name"] = UNCATEGORIZED_FOLDER_NAME
            changed = True
        if sys.get("parent_id") is not None:
            sys["parent_id"] = None
            changed = True
        if changed:
            sys["updated_at"] = now
    else:
        items.append(
            {
                "id": UNCATEGORIZED_FOLDER_ID,
                "name": UNCATEGORIZED_FOLDER_NAME,
                "parent_id": None,
                "system": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        changed = True
    return changed


def ensure_system_folders() -> None:
    items = _read_raw_file()
    if _patch_system_folder(items):
        _save_raw(items)


def _load_raw() -> list[dict[str, Any]]:
    items = _read_raw_file()
    if _patch_system_folder(items):
        _save_raw(items)
    return items


def user_folder_ids() -> set[str]:
    return {x["id"] for x in _load_raw() if not x.get("system") and x.get("id")}


def normalize_folder_id(folder_id: str | None, valid_user_folder_ids: set[str] | None = None) -> str:
    """null / 空 / 已删文件夹 → 未分类系统 id。"""
    if is_uncategorized_folder_id(folder_id):
        return UNCATEGORIZED_FOLDER_ID
    valid = valid_user_folder_ids if valid_user_folder_ids is not None else user_folder_ids()
    fid = str(folder_id or "").strip()
    if fid in valid:
        return fid
    return UNCATEGORIZED_FOLDER_ID


def list_folders() -> list[dict[str, Any]]:
    items = sorted(_load_raw(), key=lambda x: (x.get("name") or "").lower())
    return [_public(x) for x in items]


def list_user_folders() -> list[dict[str, Any]]:
    return [f for f in list_folders() if not f.get("system")]


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
    if name == UNCATEGORIZED_FOLDER_NAME:
        raise ValueError("不能使用系统保留名称")
    items = _load_raw()
    if parent_id:
        if is_system_folder(parent_id):
            raise ValueError("不能在系统文件夹下创建子文件夹")
        if not _find_raw(parent_id):
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
    if is_system_folder(folder_id):
        raise ValueError("系统文件夹不可修改")
    items = _load_raw()
    item = _find_raw(folder_id)
    if not item:
        raise ValueError("文件夹不存在")

    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("文件夹名称不能为空")
        if name == UNCATEGORIZED_FOLDER_NAME:
            raise ValueError("不能使用系统保留名称")
        item["name"] = name

    if parent_id is not _UNSET:
        if parent_id == folder_id:
            raise ValueError("不能移动到自身")
        if parent_id and is_system_folder(parent_id):
            raise ValueError("不能移动到系统文件夹")
        if parent_id and parent_id not in {x.get("id") for x in items}:
            raise ValueError("目标父文件夹不存在")
        if parent_id and parent_id in _descendant_ids(folder_id, items):
            raise ValueError("不能移动到子文件夹")
        item["parent_id"] = parent_id

    item["updated_at"] = _now_iso()
    _save_raw(items)
    return _public(item)


def delete_folder(folder_id: str) -> dict[str, Any]:
    if is_system_folder(folder_id):
        raise ValueError("系统文件夹不可删除")
    items = _load_raw()
    item = _find_raw(folder_id)
    if not item:
        raise ValueError("文件夹不存在")
    parent_id = item.get("parent_id")
    child_ids = _descendant_ids(folder_id, items)
    removed = {folder_id, *child_ids}
    remaining = [x for x in items if x.get("id") not in removed]
    for x in remaining:
        if x.get("parent_id") in removed:
            x["parent_id"] = parent_id
            x["updated_at"] = _now_iso()
    _save_raw(remaining)
    return {"deleted_id": folder_id, "moved_children_to": parent_id, "removed_descendants": list(child_ids)}


def resolve_folder_delete_target(parent_id: str | None) -> str:
    """删除文件夹后，笔记归属：有上级则上级，否则未分类。"""
    if parent_id and not is_system_folder(parent_id) and get_folder(parent_id):
        return parent_id
    return UNCATEGORIZED_FOLDER_ID


def _public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id") or "",
        "name": item.get("name") or "",
        "parent_id": item.get("parent_id"),
        "system": bool(item.get("system")),
        "created_at": item.get("created_at") or "",
        "updated_at": item.get("updated_at") or "",
    }


def descendant_folder_ids(folder_id: str) -> set[str]:
    return _descendant_ids(folder_id, _load_raw())


def load_all_folders() -> list[dict[str, Any]]:
    return _load_raw()


def _self_check() -> None:
    ensure_system_folders()
    assert get_folder(UNCATEGORIZED_FOLDER_ID) is not None
    assert get_folder(UNCATEGORIZED_FOLDER_ID)["system"] is True
    try:
        delete_folder(UNCATEGORIZED_FOLDER_ID)
        raise AssertionError("system folder should not be deletable")
    except ValueError as exc:
        assert "不可删除" in str(exc)
    try:
        update_folder(UNCATEGORIZED_FOLDER_ID, name="改")
        raise AssertionError("system folder should not be renamable")
    except ValueError as exc:
        assert "不可修改" in str(exc)
    assert normalize_folder_id(None) == UNCATEGORIZED_FOLDER_ID
    assert normalize_folder_id("missing-id") == UNCATEGORIZED_FOLDER_ID

    f1 = create_folder("测试A")
    f2 = create_folder("测试B", parent_id=f1["id"])
    assert get_folder(f2["id"])["parent_id"] == f1["id"]
    updated = update_folder(f1["id"], name="测试A改")
    assert updated["name"] == "测试A改"
    delete_folder(f1["id"])
    assert get_folder(f1["id"]) is None
    assert get_folder(f2["id"]) is None
    assert get_folder(UNCATEGORIZED_FOLDER_ID) is not None


if __name__ == "__main__":
    _self_check()
    print("folder_store self-check ok")
