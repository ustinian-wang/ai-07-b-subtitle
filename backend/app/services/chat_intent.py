"""对话轮次意图：由 LLM 结构化判断，驱动后续编排。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import AsyncOpenAI

_INTENT_SYSTEM = """你是笔记库对话的意图路由器。只输出 JSON，不要其它文字。

字段：
- mode: "read" | "query" | "write" | "classify"
  - read: 分析/问答/解释，不改库
  - query: 列出文件夹、搜索笔记、查看目录
  - write: 单条或少量笔记的移动/删除/导入/导出
  - classify: 批量按城市/规则重新分类、整理未分类
- execute_tools: bool — 本轮是否应调用工具写库（create_folder / move_records 等）
  - 用户只要方案、讨论怎么分 → false
  - 用户明确要求执行、搬过去、调用工具、自动分类落库 → true
  - 结合上文：助手刚给出分类方案，用户 ok/继续/搞下/按此执行 → true
- inject_classify_plan: bool — 是否注入批量分类预分析（classify 或批量整理时为 true）

注意：
- 「重新分类」多为 classify + execute_tools=false（先出方案）
- 「自动分类」「移动到文件夹」「一定要执行」多为 execute_tools=true
- 无实质写库需求时不要 execute_tools=true
"""

_VALID_MODES = frozenset({"read", "query", "write", "classify"})


@dataclass
class TurnIntent:
    mode: str = "read"
    execute_tools: bool = False
    inject_classify_plan: bool = False

    @property
    def tool_intent(self) -> str:
        """供 get_openai_tools 使用：classify 按 write 收窄工具集。"""
        if self.mode in ("write", "classify"):
            return "write"
        return self.mode

    @property
    def is_classify(self) -> bool:
        return self.mode == "classify" or self.inject_classify_plan


def _history_tail(history: list[dict[str, str]], n: int = 4) -> str:
    tail = history[-n:] if history else []
    lines: list[str] = []
    for m in tail:
        role = m.get("role") or "user"
        text = (m.get("content") or "").strip().replace("\n", " ")[:400]
        if text:
            lines.append(f"{role}: {text}")
    return "\n".join(lines) if lines else "（无历史）"


def parse_intent_payload(raw: str) -> TurnIntent:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return TurnIntent()
    if not isinstance(data, dict):
        return TurnIntent()
    mode = str(data.get("mode") or "read").strip().lower()
    if mode not in _VALID_MODES:
        mode = "read"
    execute = bool(data.get("execute_tools"))
    inject = bool(data.get("inject_classify_plan"))
    if mode == "classify":
        inject = True
    return TurnIntent(mode=mode, execute_tools=execute, inject_classify_plan=inject)


async def infer_turn_intent(
    client: "AsyncOpenAI",
    model: str,
    user_message: str,
    history: list[dict[str, str]],
    *,
    reference_record_ids: list[str] | None = None,
    reference_folder_ids: list[str] | None = None,
    classify_hint: str | None = None,
) -> TurnIntent:
    """LLM 判断本轮意图（单次短调用）。"""
    ref_n = len([x for x in (reference_record_ids or []) if x])
    folder_n = len([x for x in (reference_folder_ids or []) if x])
    user_block = (
        f"用户最新消息：{user_message}\n\n"
        f"当前引用：笔记 {ref_n} 条，文件夹 {folder_n} 个\n"
        f"最近对话：\n{_history_tail(history)}\n"
    )
    if classify_hint:
        user_block += f"\n分类预分析摘要：{classify_hint}\n"

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _INTENT_SYSTEM},
            {"role": "user", "content": user_block},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        stream=False,
    )
    content = (response.choices[0].message.content or "").strip()
    return parse_intent_payload(content)


def tool_choice_for_round(intent: str, round_idx: int) -> str | dict[str, object]:
    if round_idx == 0 and intent in ("write", "query"):
        return {"type": "function", "function": {"name": "list_folders"}}
    return "auto"


def _self_check() -> None:
    t = parse_intent_payload('{"mode":"classify","execute_tools":false,"inject_classify_plan":true}')
    assert t.mode == "classify" and not t.execute_tools and t.is_classify
    t2 = parse_intent_payload('{"mode":"write","execute_tools":true}')
    assert t2.execute_tools and t2.tool_intent == "write"
    assert parse_intent_payload("not json").mode == "read"


if __name__ == "__main__":
    _self_check()
    print("chat_intent ok")
