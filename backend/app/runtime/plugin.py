"""Runtime 插件接口。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.runtime.context import RunContext
    from app.runtime.tool_registry import ToolRegistry


@runtime_checkable
class RuntimePlugin(Protocol):
    """领域插件：注册工具 + 注入领域上下文。"""

    @property
    def name(self) -> str: ...

    def register_tools(self, registry: ToolRegistry) -> None: ...

    def system_prompt(self) -> str:
        """领域 system prompt 基础段。"""
        ...

    def build_reference_context(
        self,
        ctx: RunContext,
        *,
        query_mode: bool = False,
    ) -> str:
        """引用笔记/文件夹等上下文块。"""
        ...

    def enrich_planner_context(
        self,
        ctx: RunContext,
        user_message: str,
        mutate_goal: str | None,
    ) -> str:
        """mutate 规划时追加的领域提示（可选）。"""
        ...

    def repair_tool_args(
        self,
        tool_name: str,
        args: dict[str, Any],
        messages: list[dict[str, Any]],
        ctx: RunContext,
    ) -> dict[str, Any]:
        """工具参数修复（可选）。"""
        ...
