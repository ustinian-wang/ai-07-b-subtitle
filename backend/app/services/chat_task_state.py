"""对话任务状态：pending_plan 与确认执行（Phase 1 通用内核）。"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from app.services import chat_tools
from app.services.folder_store import list_user_folders

_CONFIRM_EXACT = frozenset(
    {
        "可以",
        "ok",
        "okay",
        "yes",
        "好的",
        "好",
        "行",
        "执行",
        "确认",
        "继续",
        "按此执行",
        "搞下",
        "搬过去",
        "移过去",
        "去执行",
        "开始执行",
    }
)
_ID_IN_TEXT = re.compile(r"(?:#|`|\()([a-f0-9]{12})\)?", re.I)


def detect_confirmation(user_message: str) -> bool:
    t = (user_message or "").strip().lower()
    if not t:
        return False
    if t in _CONFIRM_EXACT:
        return True
    return any(t == k or t.startswith(k) for k in ("可以", "好的", "确认执行"))


def extract_ids_from_text(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        for rid in _ID_IN_TEXT.findall(text or ""):
            rid = rid.strip().lower()
            if rid and rid not in found:
                found.append(rid)
    return found


def infer_folder_name_from_text(*texts: str) -> str | None:
    """从对话文本推断目标文件夹名（匹配已有文件夹或常见句式）。"""
    known = { (f.get("name") or "").strip(): f.get("name") for f in list_user_folders() if f.get("name") }
    lower_map = { k.lower(): v for k, v in known.items() if k }

    for text in texts:
        if not text:
            continue
        for name in known:
            if name and name in text:
                if re.search(rf"(移|放|归|入|到|进).{{0,12}}{re.escape(name)}", text):
                    return name
                if re.search(rf"{re.escape(name)}.{0,8}文件夹", text):
                    return name
        m = re.search(r"[「【]([^」】]{1,20})[」】].{0,8}文件夹", text)
        if m:
            key = m.group(1).strip().lower()
            if key in lower_map:
                return lower_map[key]
        m = re.search(r"移(?:动)?到[「【]?(\S{1,20})[」】]?(?:文件夹)?", text)
        if m:
            key = m.group(1).strip().lower()
            if key in lower_map:
                return lower_map[key]
            return m.group(1).strip()
    return None


def build_move_plan_from_history(
    history: list[dict[str, Any]],
    user_message: str,
) -> dict[str, Any] | None:
    """从最近 assistant 消息提取 id + 目标文件夹，生成可执行 plan。"""
    assistant_texts: list[str] = []
    for m in reversed(history):
        if m.get("role") == "assistant":
            assistant_texts.append(m.get("content") or "")
        if len(assistant_texts) >= 2:
            break
    ids = extract_ids_from_text(user_message, *assistant_texts)
    folder = infer_folder_name_from_text(user_message, *assistant_texts)
    if not ids or not folder:
        return None
    return {
        "goal": "move_records",
        "steps": [{"tool": "move_records", "args": {"ids": ids, "folder_name": folder}}],
    }


def plan_from_classify_actionable(plan: dict[str, Any], actionable: dict[str, Any]) -> dict[str, Any] | None:
    """将 classify 预分析转为 pending_plan。"""
    if not actionable.get("has_work"):
        return None
    steps: list[dict[str, Any]] = []
    for fname in actionable.get("folders_to_create") or []:
        steps.append({"tool": "create_folder", "args": {"name": fname}})

    groups: dict[str, list[str]] = defaultdict(list)
    name_to_id = { (f.get("name") or "").lower(): f.get("id") for f in list_user_folders() if f.get("name") }
    for fname in actionable.get("folders_to_create") or []:
        name_to_id[fname.lower()] = fname  # placeholder until create

    for item in actionable.get("pending_moves") or []:
        fname = item.get("folder_name") or ""
        rid = item.get("id")
        if fname and rid:
            groups[fname].append(rid)

    for fname, ids in groups.items():
        args: dict[str, Any] = {"ids": ids}
        fid = None
        for item in actionable.get("pending_moves") or []:
            if item.get("folder_name") == fname and item.get("folder_id"):
                fid = item["folder_id"]
                break
        if fid:
            args["folder_id"] = fid
        else:
            args["folder_name"] = fname
        steps.append({"tool": "move_records", "args": args})

    if not steps:
        return None
    return {
        "goal": "classify",
        "steps": steps,
        "meta": {
            "skip_collection": plan.get("skip_collection") or [],
            "skip_unknown": plan.get("skip_unknown") or [],
        },
    }


def execute_plan(plan: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """执行 pending_plan，返回 (tool_steps, summary)。"""
    steps_out: list[dict[str, Any]] = []
    moved_total = 0
    created: list[str] = []
    failed_moves: list[str] = []

    for step in plan.get("steps") or []:
        tool = step.get("tool") or ""
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        result = chat_tools.execute(tool, args)
        ok = True
        preview = ""
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                ok = parsed.get("ok") is not False and not parsed.get("error")
                if parsed.get("error"):
                    preview = str(parsed["error"])[:120]
                elif tool == "create_folder":
                    preview = (parsed.get("folder") or {}).get("name") or args.get("name", "")
                    if ok:
                        created.append(preview)
                elif tool == "move_records":
                    moved = parsed.get("moved") or []
                    failed = parsed.get("failed") or []
                    moved_total += len(moved)
                    failed_moves.extend(failed)
                    preview = f"moved={len(moved)}" + (f", failed={len(failed)}" if failed else "")
                elif parsed.get("count") is not None:
                    preview = f"count={parsed['count']}"
        except json.JSONDecodeError:
            preview = (result or "")[:120]

        steps_out.append(
            {
                "name": tool,
                "ok": ok,
                "preview": preview,
                "result": result,
            }
        )

    summary = {
        "records_moved": moved_total,
        "folders_created": created,
        "failed_moves": failed_moves,
        "goal": plan.get("goal"),
    }
    return steps_out, summary


def offer_move_plan_from_assistant(assistant_text: str) -> dict[str, Any] | None:
    """assistant 提供移动建议时，尝试生成 pending_plan。"""
    if not re.search(r"移动|移入|归入|放入|搬到", assistant_text or ""):
        return None
    ids = extract_ids_from_text(assistant_text)
    folder = infer_folder_name_from_text(assistant_text)
    if not ids or not folder:
        return None
    return {
        "goal": "move_records",
        "steps": [{"tool": "move_records", "args": {"ids": ids, "folder_name": folder}}],
    }


def _self_check() -> None:
    assert detect_confirmation("可以")
    assert detect_confirmation("OK")
    assert not detect_confirmation("未分类有多少")
    ids = extract_ids_from_text("见 #7368ee9aac7f 和 `83407f062c80`")
    assert len(ids) == 2
    plan = build_move_plan_from_history(
        [{"role": "assistant", "content": "移入【首尔】文件夹：#7368ee9aac7f #83407f062c80"}],
        "可以",
    )
    assert plan and plan["steps"][0]["tool"] == "move_records"
    assert plan["steps"][0]["args"]["folder_name"] == "首尔"


if __name__ == "__main__":
    _self_check()
    print("chat_task_state self-check ok")
