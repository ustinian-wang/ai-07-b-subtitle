"""工具注册表：ToolSpec + 按 intent 过滤。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

Handler = Callable[[dict[str, Any]], str]

# 操作分类（前端目录按 order 排序）
TOOL_CATEGORIES: dict[str, dict[str, Any]] = {
    "library": {"label": "笔记库", "order": 1},
    "folder": {"label": "分类", "order": 2},
    "extract": {"label": "提取", "order": 3},
    "manage": {"label": "管理", "order": 4},
}


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Handler
    category: str = "library"
    label: str = ""
    side_effect: bool = False

    def openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolRegistry:
    _specs: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    def register_many(self, specs: list[ToolSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        spec = self._specs.get(name)
        if not spec:
            return json.dumps({"ok": False, "error": f"未知工具: {name}"}, ensure_ascii=False)
        try:
            return spec.handler(arguments or {})
        except Exception as err:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False)

    def tool_category(self, name: str) -> str:
        return (self._specs.get(name) or ToolSpec("", "", {}, lambda _: "")).category or "library"

    def tool_label(self, name: str) -> str:
        spec = self._specs.get(name)
        return (spec.label if spec else None) or name

    def get_openai_tools(self, *, intent: str | None = None) -> list[dict[str, Any]]:
        allowed: set[str] | None = None
        if intent == "write":
            allowed = {"list_folders", "create_folder", "move_records"}
        elif intent == "query":
            allowed = {"list_folders", "list_records", "get_record"}
        specs = self._specs.values()
        if allowed is not None:
            specs = [s for s in specs if s.name in allowed]
        return [s.openai_tool() for s in specs]


def _self_check() -> None:
    reg = ToolRegistry()

    def echo(args: dict[str, Any]) -> str:
        return json.dumps({"ok": True, "x": args.get("x")}, ensure_ascii=False)

    reg.register(
        ToolSpec("echo", "echo", {"type": "object", "properties": {"x": {"type": "string"}}}, echo)
    )
    assert reg.tool_label("echo") == "echo"
    assert json.loads(reg.execute("echo", {"x": "1"}))["x"] == "1"
    assert reg.get_openai_tools(intent="query") == []


if __name__ == "__main__":
    _self_check()
    print("runtime.tool_registry ok")
