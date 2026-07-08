"""任务状态 FSM：idle → planning → awaiting_confirmation → executing → done。"""
from __future__ import annotations

from enum import Enum
from typing import Any


class TaskPhase(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    EXECUTING = "executing"
    DONE = "done"


_TRANSITIONS: dict[TaskPhase, frozenset[TaskPhase]] = {
    TaskPhase.IDLE: frozenset({TaskPhase.PLANNING, TaskPhase.EXECUTING}),
    TaskPhase.PLANNING: frozenset(
        {TaskPhase.AWAITING_CONFIRMATION, TaskPhase.EXECUTING, TaskPhase.DONE, TaskPhase.IDLE}
    ),
    TaskPhase.AWAITING_CONFIRMATION: frozenset({TaskPhase.EXECUTING, TaskPhase.IDLE, TaskPhase.DONE}),
    TaskPhase.EXECUTING: frozenset({TaskPhase.DONE, TaskPhase.IDLE}),
    TaskPhase.DONE: frozenset({TaskPhase.IDLE, TaskPhase.PLANNING}),
}


class TaskState:
    """轻量 FSM，与 agent.memory 持久化状态对齐。"""

    def __init__(self, phase: TaskPhase = TaskPhase.IDLE) -> None:
        self.phase = phase

    def can_transition(self, target: TaskPhase) -> bool:
        return target in _TRANSITIONS.get(self.phase, frozenset())

    def transition(self, target: TaskPhase) -> None:
        if not self.can_transition(target):
            raise ValueError(f"非法状态迁移: {self.phase.value} → {target.value}")
        self.phase = target

    @classmethod
    def from_memory(cls, mem: dict[str, Any]) -> TaskState:
        status = mem.get("status") or TaskPhase.IDLE.value
        try:
            return cls(TaskPhase(status))
        except ValueError:
            if mem.get("awaiting_confirmation"):
                return cls(TaskPhase.AWAITING_CONFIRMATION)
            return cls(TaskPhase.IDLE)

    def to_memory_patch(self) -> dict[str, str]:
        return {"status": self.phase.value}


def _self_check() -> None:
    ts = TaskState()
    ts.transition(TaskPhase.PLANNING)
    ts.transition(TaskPhase.AWAITING_CONFIRMATION)
    ts.transition(TaskPhase.EXECUTING)
    ts.transition(TaskPhase.DONE)
    ts.transition(TaskPhase.IDLE)
    mem = {"status": "awaiting_confirmation", "awaiting_confirmation": True}
    assert TaskState.from_memory(mem).phase == TaskPhase.AWAITING_CONFIRMATION


if __name__ == "__main__":
    _self_check()
    print("runtime.task_state ok")
