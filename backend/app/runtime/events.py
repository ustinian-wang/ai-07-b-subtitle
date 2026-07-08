"""运行时事件：与 SSE 传输层解耦。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StepEvent:
    """单步事件；kind 对应 SSE payload 顶层键。"""

    kind: str
    payload: dict[str, Any]

    @staticmethod
    def delta(text: str) -> StepEvent:
        return StepEvent("delta", {"delta": text})

    @staticmethod
    def tool_start(name: str, label: str, category: str, category_label: str) -> StepEvent:
        return StepEvent(
            "tool_start",
            {
                "tool_start": {
                    "name": name,
                    "label": label,
                    "category": category,
                    "category_label": category_label,
                }
            },
        )

    @staticmethod
    def tool_end(name: str, ok: bool, preview: str) -> StepEvent:
        return StepEvent("tool_end", {"tool_end": {"name": name, "ok": ok, "preview": preview}})

    @staticmethod
    def done() -> StepEvent:
        return StepEvent("done", {"done": True})

    @staticmethod
    def error(message: str) -> StepEvent:
        return StepEvent("error", {"error": message})

    @staticmethod
    def phase(name: str) -> StepEvent:
        """可选阶段标记：routing / planning / executing。"""
        return StepEvent("phase", {"phase": name})


def _self_check() -> None:
    e = StepEvent.delta("hi")
    assert e.kind == "delta" and e.payload["delta"] == "hi"
    ts = StepEvent.tool_start("list_records", "列出笔记", "library", "笔记库")
    assert ts.payload["tool_start"]["name"] == "list_records"
    assert StepEvent.done().payload["done"] is True
    assert StepEvent.phase("routing").payload["phase"] == "routing"


if __name__ == "__main__":
    _self_check()
    print("runtime.events ok")
