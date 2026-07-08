"""笔记库领域插件：工具、引用上下文、分类规则、参数修复。"""
from __future__ import annotations

import json
import re
from typing import Any

from app.runtime.context import RunContext
from app.runtime.tool_registry import ToolRegistry, ToolSpec
from app.services import chat_tools
from app.services.chat_classify_plan import build_classify_plan_block
from app.services.folder_store import get_folder, is_all_folder_id, is_uncategorized_folder_id
from app.services.subtitle_store import get_record, infer_source, list_record_ids_in_folder

SYSTEM_PROMPT = """你是笔记分析助手。用户会引用本地库中的 B 站字幕或小红书笔记作为上下文。
请优先基于引用笔记回答；若引用不足以回答，可结合常识并说明依据。
回答使用 Markdown，代码用 fenced code block。简洁准确。

你还可通过工具操作本地笔记库（查看、分类、提取链接、移动、删除、导出）。
需要实际改动库数据或拉取新笔记时调用工具；纯分析/问答时直接回答。
查未分类笔记时优先 list_records(folder_name="未分类", include_text=true)；get_record 必须带 id 或 ids。"""

REF_CHAR_LIMIT = 12000
FOLDER_REF_TOTAL_CHAR_LIMIT = 48000


class NoteLibraryPlugin:
    name = "note_library"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register_many(chat_tools.build_tool_specs())

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_reference_context(self, ctx: RunContext, *, query_mode: bool = False) -> str:
        blocks: list[str] = []
        ref_block = _build_reference_block(ctx.ref_ids)
        folder_block = _build_folder_reference_block(ctx.folder_ids, summary_only=query_mode)
        if ref_block:
            blocks.append(ref_block)
        if folder_block:
            blocks.append(folder_block)
        if query_mode and "未分类" in ctx.user_message:
            uncat = _uncategorized_query_block(ctx)
            if uncat:
                blocks.append(uncat)
        return "\n\n".join(blocks)

    def enrich_planner_context(
        self,
        ctx: RunContext,
        user_message: str,
        mutate_goal: str | None,
    ) -> str:
        if mutate_goal != "classify_by_city":
            return ""
        return build_classify_plan_block(ctx.ref_ids, ctx.folder_ids, ctx.history)

    def repair_tool_args(
        self,
        tool_name: str,
        args: dict[str, Any],
        messages: list[dict[str, Any]],
        ctx: RunContext,
    ) -> dict[str, Any]:
        return _repair_tool_args(tool_name, args, messages, ctx.user_message, ctx.registry)


def build_messages(
    ctx: RunContext,
    *,
    query_mode: bool = False,
    plugin: NoteLibraryPlugin | None = None,
) -> list[dict[str, Any]]:
    """组装 LLM messages（system + history + user）。"""
    p = plugin or NoteLibraryPlugin()
    system = p.system_prompt()
    ref_ctx = p.build_reference_context(ctx, query_mode=query_mode)
    if ref_ctx:
        system = f"{system}\n\n{ref_ctx}"

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in ctx.history:
        role = m.get("role")
        if role == "tools":
            continue
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": m.get("content") or ""})
    messages.append({"role": "user", "content": ctx.user_message})
    return messages


def _folder_display_name(folder_id: str) -> str:
    if is_all_folder_id(folder_id):
        return "全部"
    if is_uncategorized_folder_id(folder_id):
        return "未分类"
    folder = get_folder(folder_id)
    return (folder or {}).get("name") or folder_id


def _build_folder_reference_block(folder_ids: list[str], *, summary_only: bool = False) -> str:
    parts: list[str] = []
    budget = FOLDER_REF_TOTAL_CHAR_LIMIT
    for folder_id in folder_ids:
        if budget <= 0:
            parts.append("…（分类引用总字数已达上限，后续分类已省略）")
            break
        record_ids = list_record_ids_in_folder(folder_id)
        if not record_ids:
            continue
        name = _folder_display_name(folder_id)
        header = f"### [分类] {name} (#{folder_id}) · {len(record_ids)} 条笔记"
        section_parts: list[str] = [header]
        used = len(header)
        truncated = False
        for rid in record_ids:
            rec = get_record(rid)
            if not rec:
                continue
            source = infer_source(rec)
            label = "小红书" if source == "xiaohongshu" else "B站"
            title = rec.get("title") or rec.get("note_id") or rec.get("bvid") or rid
            if summary_only:
                piece = f"- [{label}] {title} (#{rid})"
            else:
                text = (rec.get("text") or "").strip()
                piece = f"#### [{label}] {title} (#{rid})\n\n{text}"
                if len(piece) > REF_CHAR_LIMIT:
                    piece = piece[:REF_CHAR_LIMIT] + "\n…（已截断）"
            if used + len(piece) + 2 > budget:
                truncated = True
                break
            section_parts.append(piece)
            used += len(piece) + 2
        if truncated:
            section_parts.append("…（该分类剩余笔记因字数上限未全部注入）")
        parts.append("\n\n".join(section_parts))
        budget -= used
    if not parts:
        return ""
    intro = (
        "以下为用户引用的本地库分类（仅标题与 id，正文请按需通过工具读取）："
        if summary_only
        else "以下为用户引用的本地库分类（含分类内笔记）："
    )
    return intro + "\n\n" + "\n\n---\n\n".join(parts)


def _build_reference_block(record_ids: list[str]) -> str:
    parts: list[str] = []
    for rid in record_ids:
        rec = get_record(rid)
        if not rec:
            continue
        source = infer_source(rec)
        label = "小红书" if source == "xiaohongshu" else "B站"
        title = rec.get("title") or rec.get("note_id") or rec.get("bvid") or rid
        text = (rec.get("text") or "").strip()
        if len(text) > REF_CHAR_LIMIT:
            text = text[:REF_CHAR_LIMIT] + "\n…（已截断）"
        parts.append(f"### [{label}] {title} (#{rid})\n\n{text}")
    if not parts:
        return ""
    return "以下为用户引用的本地库笔记：\n\n" + "\n\n---\n\n".join(parts)


def _uncategorized_query_block(ctx: RunContext) -> str:
    if "未分类" not in ctx.user_message:
        return ""
    result = ctx.registry.execute(
        "list_records",
        {"folder_name": "未分类", "include_text": True, "limit": 50},
    )
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        return ""
    if not parsed.get("ok"):
        return ""
    records = parsed.get("records") or []
    if not records:
        return "当前未分类文件夹为空。"
    lines: list[str] = []
    for rec in records:
        rid = rec.get("id") or ""
        title = rec.get("title") or rid
        text = (rec.get("text") or "").strip()
        if len(text) > 2000:
            text = text[:2000] + "\n…（已截断）"
        lines.append(f"### {title} (id={rid})\n\n{text or '（无正文）'}")
    return (
        f"以下未分类笔记正文已由系统预加载（共 {len(records)} 条），请直接分析，勿再调用 get_record：\n\n"
        + "\n\n---\n\n".join(lines)
    )


def _ids_from_recent_text(messages: list[dict[str, Any]], user_message: str) -> list[str]:
    chunks: list[str] = [user_message]
    for m in reversed(messages):
        if m.get("role") not in ("user", "assistant"):
            continue
        text = (m.get("content") or "").strip()
        if text:
            chunks.append(text)
        if len(chunks) >= 6:
            break
    found: list[str] = []
    for text in chunks:
        for rid in re.findall(r"(?:#|`)([a-f0-9]{12})\b", text, flags=re.I):
            if rid not in found:
                found.append(rid)
    return found


def _last_list_record_ids(
    messages: list[dict[str, Any]],
    registry: ToolRegistry,
    *,
    uncategorized_only: bool = False,
) -> list[str]:
    for m in reversed(messages):
        if m.get("role") != "tool":
            continue
        try:
            parsed = json.loads(m.get("content") or "")
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict) or not isinstance(parsed.get("records"), list):
            continue
        ids = [str(r.get("id") or "").strip() for r in parsed["records"] if str(r.get("id") or "").strip()]
        if ids:
            return ids
    if uncategorized_only:
        try:
            parsed = json.loads(registry.execute("list_records", {"folder_name": "未分类", "limit": 50}))
            return [str(r.get("id") or "").strip() for r in parsed.get("records") or [] if r.get("id")]
        except json.JSONDecodeError:
            pass
    return []


def _repair_tool_args(
    tool_name: str,
    args: dict[str, Any],
    messages: list[dict[str, Any]],
    user_message: str,
    registry: ToolRegistry,
) -> dict[str, Any]:
    if tool_name == "get_record":
        if chat_tools._record_id(args) or chat_tools._record_ids(args):
            return args
        uncat = "未分类" in user_message
        ids = _last_list_record_ids(messages, registry, uncategorized_only=uncat)
        if ids:
            return {"ids": ids[:20]}
    if tool_name == "move_records":
        repaired = dict(args)
        ids = chat_tools._record_ids(repaired)
        if not ids:
            ids = _ids_from_recent_text(messages, user_message)
            if ids:
                repaired["ids"] = ids
        if ids and not repaired.get("folder_name") and repaired.get("folder_id") is None:
            from app.services.chat_task_state import infer_folder_name_from_text

            chunks = [user_message]
            for m in reversed(messages):
                if m.get("role") in ("user", "assistant"):
                    t = (m.get("content") or "").strip()
                    if t:
                        chunks.append(t)
                if len(chunks) >= 6:
                    break
            folder = infer_folder_name_from_text(*chunks)
            if folder:
                repaired["folder_name"] = folder
        if repaired.get("folder_name"):
            resolved = chat_tools.resolve_folder_name(str(repaired["folder_name"]))
            if resolved:
                repaired["folder_name"] = resolved
        if chat_tools._record_ids(repaired):
            return repaired
    return args


def _self_check() -> None:
    from app.runtime.tool_registry import ToolRegistry

    reg = ToolRegistry()
    plugin = NoteLibraryPlugin()
    plugin.register_tools(reg)
    assert len(reg.get_openai_tools()) == 8
    assert plugin.system_prompt().startswith("你是笔记分析助手")
    ctx = RunContext(
        thread_id="t",
        user_message="总结",
        history=[],
        ref_ids=[],
        folder_ids=[],
        client=None,  # type: ignore[arg-type]
        model="m",
        registry=reg,
        plugins=(plugin,),
    )
    msgs = build_messages(ctx)
    assert msgs[0]["role"] == "system"
    assert plugin.repair_tool_args("get_record", {}, [], ctx) == {}


if __name__ == "__main__":
    _self_check()
    print("runtime.plugins.note_library ok")
