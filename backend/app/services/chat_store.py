"""对话会话：本地 JSON 持久化（单用户 demo）。"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT


def _sessions_dir() -> Path:
    d = BACKEND_ROOT / "data" / "chat_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _thread_path(thread_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", thread_id).strip("._-")[:180]
    if not safe:
        raise ValueError("invalid thread id")
    return _sessions_dir() / f"{safe}.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _derive_title(messages: list[dict[str, str]]) -> str:
    for m in messages:
        if m.get("role") == "user":
            t = (m.get("content") or "").strip().replace("\n", " ")
            if t:
                return t[:80]
    return "新对话"


def get_messages(thread_id: str) -> list[dict[str, str]]:
    path = _thread_path(thread_id)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError):
        return []
    if isinstance(raw, dict) and isinstance(raw.get("messages"), list):
        return _normalize(raw["messages"])
    if isinstance(raw, list):
        return _normalize(raw)
    return []


def save_messages(thread_id: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    path = _thread_path(thread_id)
    now = _now_iso()
    prev = _read_thread_file(path) or {}
    payload = {
        "thread_id": thread_id,
        "created_at": prev.get("created_at") or now,
        "updated_at": now,
        "title": _derive_title(messages),
        "messages": _normalize(messages),
        "task_state": prev.get("task_state") if isinstance(prev.get("task_state"), dict) else {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get_task_state(thread_id: str) -> dict[str, Any]:
    snap = _read_thread_file(_thread_path(thread_id)) or {}
    ts = snap.get("task_state")
    return dict(ts) if isinstance(ts, dict) else {}


def save_task_state(thread_id: str, task_state: dict[str, Any] | None) -> None:
    path = _thread_path(thread_id)
    snap = _read_thread_file(path) or {
        "thread_id": thread_id,
        "created_at": _now_iso(),
        "messages": [],
    }
    snap["task_state"] = task_state if isinstance(task_state, dict) else {}
    snap["updated_at"] = _now_iso()
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")


def set_pending_plan(thread_id: str, plan: dict[str, Any] | None) -> None:
    state = get_task_state(thread_id)
    if plan:
        state["pending_plan"] = plan
    else:
        state.pop("pending_plan", None)
    save_task_state(thread_id, state)


def get_pending_plan(thread_id: str) -> dict[str, Any] | None:
    plan = get_task_state(thread_id).get("pending_plan")
    return plan if isinstance(plan, dict) else None


def append_exchange(thread_id: str, user: str, assistant: str) -> list[dict[str, Any]]:
    return append_turn(thread_id, user, assistant, tool_steps=None)


def append_turn(
    thread_id: str,
    user: str,
    assistant: str,
    tool_steps: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    msgs = get_messages(thread_id)
    msgs.append({"role": "user", "content": user})
    steps = _normalize_steps(tool_steps or [])
    if steps:
        msgs.append({"role": "tools", "steps": steps})
    msgs.append({"role": "assistant", "content": assistant})
    save_messages(thread_id, msgs)
    return msgs


def clear_thread(thread_id: str) -> None:
    delete_thread(thread_id)


def create_thread(thread_id: str | None = None) -> str:
    tid = (thread_id or "").strip() or uuid.uuid4().hex[:12]
    now = _now_iso()
    path = _thread_path(tid)
    if not path.is_file():
        payload = {
            "thread_id": tid,
            "created_at": now,
            "updated_at": now,
            "title": "新对话",
            "messages": [],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return tid


def _read_thread_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def list_threads() -> list[dict[str, Any]]:
    """列出全部会话，按 updated_at 倒序。"""
    out: list[dict[str, Any]] = []
    for path in _sessions_dir().glob("*.json"):
        snap = _read_thread_file(path)
        if not snap:
            continue
        tid = str(snap.get("thread_id") or path.stem)
        msgs = _normalize(snap.get("messages") or [])
        title = str(snap.get("title") or "").strip() or _derive_title(msgs)
        out.append(
            {
                "thread_id": tid,
                "title": title[:120],
                "updated_at": snap.get("updated_at") or snap.get("created_at") or "",
                "message_count": len(msgs),
            }
        )
    out = [x for x in out if x["message_count"] > 0]
    out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return out


def delete_thread(thread_id: str) -> bool:
    path = _thread_path(thread_id)
    if not path.is_file():
        return False
    path.unlink()
    return True


def _normalize_step(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(raw.get("name") or ""),
        "label": str(raw.get("label") or raw.get("name") or ""),
        "category_label": str(raw.get("category_label") or raw.get("categoryLabel") or ""),
        "ok": bool(raw.get("ok", True)),
        "preview": str(raw.get("preview") or ""),
        "status": str(raw.get("status") or "done"),
    }


def _normalize_steps(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        step = _normalize_step(item)
        if step["name"]:
            out.append(step)
    return out


def _normalize(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in raw:
        role = str(m.get("role", ""))
        if role == "tools":
            steps = _normalize_steps(m.get("steps") if isinstance(m.get("steps"), list) else [])
            if steps:
                out.append({"role": "tools", "steps": steps})
            continue
        if role not in ("user", "assistant"):
            continue
        content = m.get("content")
        if content is None:
            continue
        out.append({"role": role, "content": str(content)})
    return out


def _self_check() -> None:
    tid = create_thread()
    append_exchange(tid, "你好", "你好，有什么可以帮你？")
    assert len(get_messages(tid)) == 2
    append_turn(
        tid,
        "查一下",
        "已列出笔记。",
        tool_steps=[{"name": "list_records", "label": "列出笔记", "ok": True, "preview": "count=3"}],
    )
    msgs = get_messages(tid)
    assert len(msgs) == 5
    assert msgs[3]["role"] == "tools"
    assert msgs[3]["steps"][0]["name"] == "list_records"
    listed = list_threads()
    assert any(x["thread_id"] == tid for x in listed)
    row = next(x for x in listed if x["thread_id"] == tid)
    assert row["message_count"] == 5
    set_pending_plan(tid, {"goal": "test", "steps": []})
    assert get_pending_plan(tid)["goal"] == "test"
    set_pending_plan(tid, None)
    assert get_pending_plan(tid) is None
    delete_thread(tid)
    assert get_messages(tid) == []


if __name__ == "__main__":
    _self_check()
    print("chat_store self-check ok")
