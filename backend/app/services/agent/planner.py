"""Agent 规划器：产出结构化 Plan（goal + steps + requires_confirmation）。"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from app.services import chat_tools
from app.services.chat_classify_plan import (
    build_classify_plan,
    plan_actionable_work,
    resolve_classify_refs,
)
from app.services.chat_task_state import (
    build_move_plan_from_history,
    extract_ids_from_text,
    infer_folder_name_from_text,
    plan_from_classify_actionable,
)
from app.services.folder_store import UNCATEGORIZED_FOLDER_ID, list_folders
from app.services.subtitle_store import list_record_ids_in_folder

if TYPE_CHECKING:
    from openai import AsyncOpenAI

_CLASSIFY_RE = re.compile(r"分类|整理|分城市|自动分类|重新分类|按城市")
_MOVE_RE = re.compile(r"移|搬|放|归|入到|放进")
_UNCAT_RE = re.compile(r"未分类")

_PLANNER_SYSTEM = """你是笔记库变更规划器。只输出 JSON，不要其它文字。

输出 schema：
{
  "goal": "move_records" | "classify_by_city" | "generic",
  "requires_confirmation": bool,
  "steps": [
    {"tool": "list_folders|list_records|create_folder|move_records|delete_records|...", "args": {...}}
  ],
  "meta": {"reason": "可选说明"}
}

规则：
- steps 必须可直接执行；move_records 需 ids + folder_name 或 folder_id
- 移到未分类时 folder_name 必须是「未分类」（不是「未分类下」）
- 批量移动同一目标可合并为一条 move_records
- 用户仅要方案时 requires_confirmation=true 且 steps 可为空（由 meta 说明）
- 用户明确要求执行时 requires_confirmation=false
"""


def _normalize_plan(raw: dict[str, Any], *, default_goal: str = "generic") -> dict[str, Any]:
    steps = raw.get("steps") if isinstance(raw.get("steps"), list) else []
    clean_steps: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        tool = str(step.get("tool") or "").strip()
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        if tool:
            clean_steps.append({"tool": tool, "args": args})
    return {
        "goal": str(raw.get("goal") or default_goal),
        "steps": clean_steps,
        "requires_confirmation": bool(raw.get("requires_confirmation")),
        "meta": raw.get("meta") if isinstance(raw.get("meta"), dict) else {},
    }


def infer_mutate_goal(user_message: str) -> str:
    """从用户消息推断 mutate 子目标。"""
    if _CLASSIFY_RE.search(user_message or ""):
        return "classify_by_city"
    if _MOVE_RE.search(user_message or ""):
        return "move_records"
    return "generic"


def plan_classify(
    ref_ids: list[str],
    folder_ids: list[str],
    history: list[dict[str, Any]],
    *,
    auto_execute: bool,
) -> dict[str, Any]:
    eff_ref, eff_folder = resolve_classify_refs(ref_ids, folder_ids, history)
    analysis = build_classify_plan(eff_ref, eff_folder, history)
    actionable = plan_actionable_work(analysis)
    plan = plan_from_classify_actionable(analysis, actionable)
    plan["requires_confirmation"] = not auto_execute
    plan["meta"] = {
        **(plan.get("meta") or {}),
        "analysis": {
            "total_scanned": analysis.get("total_scanned"),
            "skip_collection": len(analysis.get("skip_collection") or []),
            "skip_unknown": len(analysis.get("skip_unknown") or []),
        },
    }
    return plan


def _ids_outside_uncategorized() -> list[str]:
    """所有不在未分类的直接归属笔记 id。"""
    all_ids: set[str] = set()
    for folder in list_folders():
        fid = folder.get("id") or ""
        if not fid or fid == UNCATEGORIZED_FOLDER_ID:
            continue
        for rid in list_record_ids_in_folder(fid):
            all_ids.add(rid)
    return sorted(all_ids)


def plan_move(
    user_message: str,
    history: list[dict[str, Any]],
    *,
    auto_execute: bool,
) -> dict[str, Any] | None:
    """移动类 plan：从历史/消息提取 ids + 目标文件夹。"""
    from_history = build_move_plan_from_history(history, user_message)
    if from_history:
        from_history["requires_confirmation"] = not auto_execute
        return from_history

    ids = extract_ids_from_text(user_message)
    if not ids:
        for m in reversed(history):
            if m.get("role") == "assistant":
                ids = extract_ids_from_text(m.get("content") or "")
                if ids:
                    break

    folder = infer_folder_name_from_text(user_message)
    if not folder:
        chunks = [user_message]
        for m in reversed(history):
            if m.get("role") in ("user", "assistant"):
                t = (m.get("content") or "").strip()
                if t:
                    chunks.append(t)
            if len(chunks) >= 4:
                break
        folder = infer_folder_name_from_text(*chunks)

    # 「其他目录/全部笔记 → 未分类」
    if _UNCAT_RE.search(user_message or "") and _MOVE_RE.search(user_message or ""):
        if re.search(r"其他|全部|所有|其余", user_message or ""):
            ids = _ids_outside_uncategorized()
            folder = "未分类"
        elif not ids:
            ids = _ids_outside_uncategorized()
            folder = folder or "未分类"

    if ids and folder:
        resolved = chat_tools.resolve_folder_name(folder) or folder
        return {
            "goal": "move_records",
            "steps": [{"tool": "move_records", "args": {"ids": ids, "folder_name": resolved}}],
            "requires_confirmation": not auto_execute,
            "meta": {"record_count": len(ids), "folder_name": resolved},
        }
    return None


def plan_for_confirm(
    pending_plan: dict[str, Any] | None,
    history: list[dict[str, Any]],
    user_message: str,
) -> dict[str, Any] | None:
    if pending_plan and pending_plan.get("steps") is not None:
        return pending_plan
    return build_move_plan_from_history(history, user_message)


async def plan_mutate(
    client: "AsyncOpenAI",
    model: str,
    user_message: str,
    history: list[dict[str, Any]],
    *,
    mutate_goal: str | None,
    auto_execute: bool,
    ref_ids: list[str],
    folder_ids: list[str],
) -> dict[str, Any]:
    goal = mutate_goal or infer_mutate_goal(user_message)

    if goal == "classify_by_city":
        return plan_classify(ref_ids, folder_ids, history, auto_execute=auto_execute)

    if goal == "move_records":
        move_plan = plan_move(user_message, history, auto_execute=auto_execute)
        if move_plan:
            return move_plan

    # generic：LLM 结构化规划
    context = _planner_context(user_message, history, ref_ids, folder_ids)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _PLANNER_SYSTEM},
            {"role": "user", "content": context},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        stream=False,
    )
    raw = json.loads(response.choices[0].message.content or "{}")
    plan = _normalize_plan(raw if isinstance(raw, dict) else {}, default_goal=goal)
    if "requires_confirmation" not in (raw if isinstance(raw, dict) else {}):
        plan["requires_confirmation"] = not auto_execute
    # 规范化 move steps 里的 folder_name
    for step in plan.get("steps") or []:
        if step.get("tool") == "move_records":
            args = step.get("args") or {}
            if args.get("folder_name"):
                args["folder_name"] = chat_tools.resolve_folder_name(str(args["folder_name"])) or args["folder_name"]
    return plan


def _planner_context(
    user_message: str,
    history: list[dict[str, Any]],
    ref_ids: list[str],
    folder_ids: list[str],
) -> str:
    folders = list_folders()
    folder_line = ", ".join(f"{f.get('name')}({f.get('id')})" for f in folders[:20])
    tail: list[str] = []
    for m in (history or [])[-4:]:
        role = m.get("role") or "user"
        text = (m.get("content") or "").strip().replace("\n", " ")[:500]
        if text:
            tail.append(f"{role}: {text}")
    return (
        f"用户请求：{user_message}\n"
        f"引用笔记 id：{ref_ids or '无'}\n"
        f"引用文件夹 id：{folder_ids or '无'}\n"
        f"已有文件夹：{folder_line}\n"
        f"最近对话：\n" + ("\n".join(tail) if tail else "（无）")
    )


def presentation_hint(plan: dict[str, Any]) -> str:
    """供 LLM 展示方案时的系统提示。"""
    goal = plan.get("goal") or "generic"
    steps = plan.get("steps") or []
    meta = plan.get("meta") or {}
    if not steps:
        reason = meta.get("reason") or "当前无需执行写库操作"
        return f"请用 Markdown 说明现状，不要调用工具。原因：{reason}"
    if goal == "classify_by_city":
        return (
            "请基于下方方案 JSON 用 Markdown 表格展示分类计划（新建文件夹、移动、跳过项）。"
            "本轮不要调用工具；告知用户确认后可执行。"
        )
    return (
        "请基于下方方案 JSON 用 Markdown 简要列出将执行的操作（工具步骤摘要）。"
        "本轮不要调用工具；告知用户确认后可执行。"
    )


def execution_hint(plan: dict[str, Any], summary: dict[str, Any]) -> str:
    """执行完成后的汇报提示。"""
    goal = plan.get("goal") or ""
    if goal == "classify_by_city":
        return (
            f"系统已执行方案，结果 JSON：\n{json.dumps(summary, ensure_ascii=False)}\n"
            "请用 Markdown 汇报：新建文件夹、移动条数、跳过合集/未识别数量。"
        )
    return (
        f"系统已执行方案，结果 JSON：\n{json.dumps(summary, ensure_ascii=False)}\n"
        "请用 Markdown 简要汇报执行结果与失败项（如有）。"
    )


def _self_check() -> None:
    p = plan_classify([], [], [], auto_execute=False)
    assert p["goal"] == "classify"
    assert p["requires_confirmation"] is True
    m = plan_move("移到未分类下", [], auto_execute=True)
    assert m and m["steps"][0]["args"]["folder_name"] == "未分类"
    assert infer_mutate_goal("按城市分类") == "classify_by_city"
    assert infer_mutate_goal("移到首尔") == "move_records"


if __name__ == "__main__":
    _self_check()
    print("agent.planner ok")
