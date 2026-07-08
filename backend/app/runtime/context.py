"""运行上下文：一次对话轮次的共享状态。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from app.runtime.plugin import RuntimePlugin
    from app.runtime.tool_registry import ToolRegistry


@dataclass
class RunContext:
    thread_id: str
    user_message: str
    history: list[dict[str, Any]]
    ref_ids: list[str]
    folder_ids: list[str]
    client: AsyncOpenAI
    model: str
    registry: ToolRegistry
    plugins: tuple[RuntimePlugin, ...] = ()
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    mem: dict[str, Any] = field(default_factory=dict)

    @property
    def pending_plan(self) -> dict[str, Any] | None:
        plan = self.mem.get("pending_plan")
        return plan if isinstance(plan, dict) else None

    @property
    def awaiting_confirmation(self) -> bool:
        return bool(self.mem.get("awaiting_confirmation"))

    def plugin(self, name: str) -> RuntimePlugin | None:
        for p in self.plugins:
            if p.name == name:
                return p
        return None


def _self_check() -> None:
    ctx = RunContext(
        thread_id="t1",
        user_message="hi",
        history=[],
        ref_ids=[],
        folder_ids=[],
        client=None,  # type: ignore[arg-type]
        model="gpt-4o-mini",
        registry=None,  # type: ignore[arg-type]
    )
    assert ctx.run_id and len(ctx.run_id) == 12
    assert ctx.pending_plan is None


if __name__ == "__main__":
    _self_check()
    print("runtime.context ok")
