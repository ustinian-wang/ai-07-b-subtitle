"""对话任务状态：pending_plan 与确认执行（Phase 1 通用内核）。"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from app.services import chat_tools
from app.services.folder_store import list_folders

_CONFIRM_EXACT = frozenset(
    {
        "可以",
        "ok",
        "okay",
        "yes",
        "好的",
        "好",
        "好呀",
        "好啊",
        "行",
        "行啊",
        "执行",
        "确认",
        "继续",
        "按此执行",
        "搞下",
        "搬过去",
        "移过去",
        "去执行",
        "开始执行",
        "去",
        "愿意",
        "嗯",
        "嗯嗯",
        "同意",
    }
)
_DENY_PREFIX = ("不", "别", "不要", "取消", "算了", "不用")
_ID_IN_TEXT = re.compile(r"(?:#|`|\()([a-f0-9]{12})\)?", re.I)
_TABLE_ROW_ID = re.compile(r"`([a-f0-9]{12})`", re.I)
_TABLE_ROW_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def _is_denial(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if t in ("no", "n", "否"):
        return True
    return any(t == p or t.startswith(p) for p in _DENY_PREFIX)


def detect_confirmation(
    user_message: str,
    *,
    pending_plan: dict[str, Any] | None = None,
    awaiting_confirmation: bool = False,
) -> bool:
    t = (user_message or "").strip().lower()
    if not t:
        return False
    if t in _CONFIRM_EXACT:
        return True
    if any(t == k or t.startswith(k) for k in ("可以", "好的", "确认执行")):
        return True
    if re.search(r"直接移动|真正执行|立刻执行|马上执行|执行移动", t):
        return True
    # ponytail: 有待确认方案时，短句非否定回复视为确认
    if pending_plan or awaiting_confirmation:
        if len(t) <= 8 and not _is_denial(t):
            return True
    return False


def extract_ids_from_text(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        for rid in _ID_IN_TEXT.findall(text or ""):
            rid = rid.strip().lower()
            if rid and rid not in found:
                found.append(rid)
    return found


def infer_folder_name_from_text(*texts: str) -> str | None:
    """从对话文本推断目标文件夹名（与 chat_tools.resolve_folder_name 对齐）。"""
    known = {
        (f.get("name") or "").strip(): f.get("name")
        for f in list_folders()
        if f.get("name")
    }
    lower_map = {k.lower(): v for k, v in known.items() if k}

    for text in texts:
        if not text:
            continue
        for name in known:
            if name and name in text:
                if re.search(rf"(移|放|归|入|到|进).{{0,12}}{re.escape(name)}", text):
                    return chat_tools.resolve_folder_name(name) or name
                if re.search(rf"{re.escape(name)}.{0,8}文件夹", text):
                    return chat_tools.resolve_folder_name(name) or name
        m = re.search(r"[「【]([^」】]{1,20})[」】].{0,8}文件夹", text)
        if m:
            resolved = chat_tools.resolve_folder_name(m.group(1))
            if resolved:
                return resolved
        m = re.search(r"移(?:动)?到[「【]?(\S{1,20})[」】]?(?:文件夹)?", text)
        if m:
            resolved = chat_tools.resolve_folder_name(m.group(1))
            if resolved:
                return resolved
            key = chat_tools.normalize_folder_name(m.group(1)).lower()
            if key in lower_map:
                return lower_map[key]
    return None


def extract_move_mappings_from_text(text: str) -> list[tuple[str, str]]:
    """从 assistant Markdown 表格解析 (record_id, folder_name)。"""
    mappings: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    known = {
        (f.get("name") or "").strip().lower(): f.get("name")
        for f in list_folders()
        if f.get("name")
    }
    for line in (text or "").splitlines():
        if not line.strip().startswith("|"):
            continue
        if re.match(r"^\|[-\s|:]+\|$", line.strip()):
            continue
        if "ID" in line and ("标题" in line or "建议" in line):
            continue
        rid_m = _TABLE_ROW_ID.search(line)
        if not rid_m:
            continue
        rid = rid_m.group(1).lower()
        folder = None
        for bold in reversed(_TABLE_ROW_BOLD.findall(line)):
            candidate = bold.split("（")[0].split("(")[0].strip()
            resolved = chat_tools.resolve_folder_name(candidate)
            if resolved:
                folder = resolved
                break
            if candidate.lower() in known:
                folder = known[candidate.lower()]
                break
        if folder and (rid, folder) not in seen:
            seen.add((rid, folder))
            mappings.append((rid, folder))
    return mappings


def build_move_plan_from_mappings(mappings: list[tuple[str, str]]) -> dict[str, Any] | None:
    if not mappings:
        return None
    groups: dict[str, list[str]] = defaultdict(list)
    for rid, folder in mappings:
        groups[folder].append(rid)
    steps: list[dict[str, Any]] = []
    for folder, ids in groups.items():
        resolved = chat_tools.resolve_folder_name(folder) or folder
        steps.append({"tool": "move_records", "args": {"ids": ids, "folder_name": resolved}})
    return {"goal": "move_records", "steps": steps, "meta": {"record_count": len(mappings)}}


def build_move_plan_from_history(
    history: list[dict[str, Any]],
    user_message: str,
) -> dict[str, Any] | None:
    """从最近 assistant 消息提取 id + 目标文件夹，生成可执行 plan。"""
    assistant_texts: list[str] = []
    for m in reversed(history):
        if m.get("role") == "assistant":
            assistant_texts.append(m.get("content") or "")
        if len(assistant_texts) >= 3:
            break

    for text in assistant_texts:
        mappings = extract_move_mappings_from_text(text)
        if mappings:
            return build_move_plan_from_mappings(mappings)

    ids = extract_ids_from_text(user_message, *assistant_texts)
    folder = infer_folder_name_from_text(user_message, *assistant_texts)
    if not ids or not folder:
        return None
    return {
        "goal": "move_records",
        "steps": [{"tool": "move_records", "args": {"ids": ids, "folder_name": folder}}],
    }


def build_move_to_uncategorized_plan(ids: list[str]) -> dict[str, Any]:
    return {
        "goal": "move_records",
        "steps": [
            {"tool": "move_records", "args": {"ids": ids, "folder_name": "未分类"}},
        ],
    }


def plan_from_classify_actionable(plan: dict[str, Any], actionable: dict[str, Any]) -> dict[str, Any]:
    """将 classify 预分析转为 pending_plan（无工作时也写入显式 plan）。"""
    meta = {
        "skip_collection": plan.get("skip_collection") or [],
        "skip_unknown": plan.get("skip_unknown") or [],
    }
    if not actionable.get("has_work"):
        return {
            "goal": "classify",
            "steps": [],
            "meta": {**meta, "reason": "当前引用范围内无需新建文件夹或移动笔记"},
        }

    steps: list[dict[str, Any]] = []
    for fname in actionable.get("folders_to_create") or []:
        steps.append({"tool": "create_folder", "args": {"name": fname}})

    groups: dict[str, list[str]] = defaultdict(list)
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

    return {
        "goal": "classify",
        "steps": steps,
        "meta": meta,
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
    if not re.search(r"移动|移入|归入|放入|搬到|建议移动", assistant_text or ""):
        return None
    mappings = extract_move_mappings_from_text(assistant_text)
    if mappings:
        return build_move_plan_from_mappings(mappings)
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
    assert detect_confirmation("去")
    assert detect_confirmation("愿意")
    assert detect_confirmation("嗯", awaiting_confirmation=True)
    assert not detect_confirmation("未分类有多少")
    assert not detect_confirmation("不要", awaiting_confirmation=True)
    assert infer_folder_name_from_text("移到未分类下") == "未分类"
    assert chat_tools.normalize_folder_name("首尔下") == "首尔"
    ids = extract_ids_from_text("见 #7368ee9aac7f 和 `83407f062c80`")
    assert len(ids) == 2
    plan = build_move_plan_from_history(
        [{"role": "assistant", "content": "移入【首尔】文件夹：#7368ee9aac7f #83407f062c80"}],
        "可以",
    )
    assert plan and plan["steps"][0]["tool"] == "move_records"
    assert plan["steps"][0]["args"]["folder_name"] == "首尔"
    table_plan = build_move_plan_from_history(
        [
            {
                "role": "assistant",
                "content": (
                    "| ID | 标题 | 建议移动到 |\n"
                    "|---|---|---|\n"
                    "| `7368ee9aac7f` | a | **首尔** |\n"
                    "| `83407f062c80` | b | **江原道** |"
                ),
            }
        ],
        "直接移动",
    )
    assert table_plan and len(table_plan["steps"]) == 2
    empty = plan_from_classify_actionable({"skip_collection": [], "skip_unknown": []}, {"has_work": False})
    assert empty["goal"] == "classify" and empty["meta"].get("reason")
    uncat = build_move_to_uncategorized_plan(["abc123"])
    assert uncat["steps"][0]["args"]["folder_name"] == "未分类"


if __name__ == "__main__":
    _self_check()
    print("chat_task_state self-check ok")
