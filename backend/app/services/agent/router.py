"""Agent 路由：只判交互类型，不产出工具参数。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.services.chat_task_state import detect_confirmation, _is_denial

if TYPE_CHECKING:
    from openai import AsyncOpenAI

_VALID_KINDS = frozenset({"read", "query", "mutate", "confirm", "cancel"})
_VALID_GOALS = frozenset({"classify_by_city", "move_records", "generic"})

_ROUTER_SYSTEM = """你是笔记库对话的路由器。只输出 JSON，不要其它文字。

字段：
- kind: "read" | "query" | "mutate" | "cancel"
  - read: 分析、解释、问答，不改库
  - query: 列出/搜索/统计笔记或文件夹
  - mutate: 任何会改动笔记库的操作（移动、分类、删除、建文件夹、导入导出）
  - cancel: 用户明确取消/不要执行待确认方案
- mutate_goal: "classify_by_city" | "move_records" | "generic" | null
  - classify_by_city: 批量按城市/规则整理、自动分类未分类
  - move_records: 明确移动指定笔记到某文件夹（含移回未分类）
  - generic: 其它写库操作或复合变更
- auto_execute: bool — 用户是否明确要求立刻执行（如「执行」「搬过去」「自动分类落库」）
  - 仅要方案/讨论/如果… → false
  - 明确执行/确认落库 → true

注意：
- 不要输出工具名或工具参数
- 有待确认方案时，用户短句确认 → 由规则层处理，勿在此重复判 confirm
"""


@dataclass
class RouteDecision:
    kind: str = "read"
    mutate_goal: str | None = None
    auto_execute: bool = False

    @property
    def is_mutate(self) -> bool:
        return self.kind == "mutate"


def _history_tail(history: list[dict[str, str]], n: int = 4) -> str:
    tail = history[-n:] if history else []
    lines: list[str] = []
    for m in tail:
        role = m.get("role") or "user"
        text = (m.get("content") or "").strip().replace("\n", " ")[:400]
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines) if lines else "（无历史）"


def route_by_rules(
    user_message: str,
    *,
    pending_plan: dict[str, Any] | None,
    awaiting_confirmation: bool,
) -> RouteDecision | None:
    """规则层：确认 / 取消优先于 LLM。"""
    if detect_confirmation(
        user_message,
        pending_plan=pending_plan,
        awaiting_confirmation=awaiting_confirmation,
    ):
        if pending_plan and pending_plan.get("steps"):
            return RouteDecision(kind="confirm")
        if awaiting_confirmation:
            return RouteDecision(kind="confirm")
    if (pending_plan or awaiting_confirmation) and _is_denial(user_message):
        return RouteDecision(kind="cancel")
    return None


def parse_route_payload(raw: str) -> RouteDecision:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return RouteDecision()
    if not isinstance(data, dict):
        return RouteDecision()
    kind = str(data.get("kind") or "read").strip().lower()
    if kind not in _VALID_KINDS or kind == "confirm":
        kind = "read"
    goal = data.get("mutate_goal")
    if goal is not None:
        goal = str(goal).strip().lower()
        if goal not in _VALID_GOALS:
            goal = "generic"
    return RouteDecision(
        kind=kind,
        mutate_goal=goal,
        auto_execute=bool(data.get("auto_execute")),
    )


async def route(
    client: "AsyncOpenAI",
    model: str,
    user_message: str,
    history: list[dict[str, str]],
    *,
    pending_plan: dict[str, Any] | None = None,
    awaiting_confirmation: bool = False,
    reference_record_ids: list[str] | None = None,
    reference_folder_ids: list[str] | None = None,
) -> RouteDecision:
    ruled = route_by_rules(
        user_message,
        pending_plan=pending_plan,
        awaiting_confirmation=awaiting_confirmation,
    )
    if ruled:
        return ruled

    ref_n = len([x for x in (reference_record_ids or []) if x])
    folder_n = len([x for x in (reference_folder_ids or []) if x])
    pending_hint = ""
    if pending_plan:
        pending_hint = f"\n当前待确认方案 goal={pending_plan.get('goal')} steps={len(pending_plan.get('steps') or [])}\n"

    user_block = (
        f"用户最新消息：{user_message}\n\n"
        f"引用：笔记 {ref_n} 条，文件夹 {folder_n} 个\n"
        f"待确认：{awaiting_confirmation}\n"
        f"{pending_hint}"
        f"最近对话：\n{_history_tail(history)}\n"
    )

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _ROUTER_SYSTEM},
            {"role": "user", "content": user_block},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        stream=False,
    )
    content = (response.choices[0].message.content or "").strip()
    return parse_route_payload(content)


def _self_check() -> None:
    assert route_by_rules("可以", pending_plan={"steps": []}, awaiting_confirmation=True).kind == "confirm"
    assert route_by_rules("不要", pending_plan={"steps": []}, awaiting_confirmation=True).kind == "cancel"
    r = parse_route_payload('{"kind":"mutate","mutate_goal":"move_records","auto_execute":true}')
    assert r.is_mutate and r.mutate_goal == "move_records" and r.auto_execute


if __name__ == "__main__":
    _self_check()
    print("agent.router ok")
