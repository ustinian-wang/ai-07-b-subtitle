"""StepEvent → SSE 行适配。"""
from __future__ import annotations

import json

from app.runtime.events import StepEvent


def event_to_sse(event: StepEvent) -> str:
    """将 StepEvent 序列化为 `data: {...}\\n\\n` 行。"""
    return f"data: {json.dumps(event.payload, ensure_ascii=False)}\n\n"


def _self_check() -> None:
    line = event_to_sse(StepEvent.delta("测试"))
    assert line.startswith("data: ")
    assert '"delta"' in line
    assert line.endswith("\n\n")
    phase_line = event_to_sse(StepEvent.phase("routing"))
    assert '"phase"' in phase_line and '"routing"' in phase_line


if __name__ == "__main__":
    _self_check()
    print("runtime.sse ok")
