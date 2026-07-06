"""Agent 执行器：确定性执行 Plan。"""
from __future__ import annotations

from typing import Any

from app.services.chat_task_state import execute_plan

__all__ = ["run_plan", "execute_plan"]


def run_plan(plan: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """执行 plan.steps，返回 (exec_steps, summary)。"""
    return execute_plan(plan)


def _self_check() -> None:
    steps, summary = run_plan({"goal": "noop", "steps": []})
    assert steps == [] and summary.get("records_moved") == 0


if __name__ == "__main__":
    _self_check()
    print("agent.executor ok")
