"""Agent 会话记忆 / 任务状态。"""
from __future__ import annotations

from typing import Any

from app.services import chat_store

STATUS_IDLE = "idle"
STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
STATUS_EXECUTING = "executing"


def load(thread_id: str) -> dict[str, Any]:
    state = chat_store.get_task_state(thread_id)
    return {
        "status": state.get("status") or STATUS_IDLE,
        "pending_plan": state.get("pending_plan"),
        "awaiting_confirmation": bool(state.get("awaiting_confirmation")),
    }


def save_pending(thread_id: str, plan: dict[str, Any]) -> None:
    state = chat_store.get_task_state(thread_id)
    state["pending_plan"] = plan
    state["awaiting_confirmation"] = True
    state["status"] = STATUS_AWAITING_CONFIRMATION
    chat_store.save_task_state(thread_id, state)


def clear_pending(thread_id: str) -> None:
    chat_store.set_pending_plan(thread_id, None)
    state = chat_store.get_task_state(thread_id)
    state["status"] = STATUS_IDLE
    chat_store.save_task_state(thread_id, state)


def _self_check() -> None:
    tid = chat_store.create_thread()
    save_pending(tid, {"goal": "test", "steps": []})
    mem = load(tid)
    assert mem["awaiting_confirmation"] and mem["pending_plan"]["goal"] == "test"
    clear_pending(tid)
    assert load(tid)["status"] == STATUS_IDLE
    chat_store.delete_thread(tid)


if __name__ == "__main__":
    _self_check()
    print("agent.memory ok")
