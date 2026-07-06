"""OpenAI 兼容 SSE 对话（可引用本地库记录 + 内置工具）。"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.services import chat_store, chat_tools, settings_store
from app.services.agent.router import RouteDecision
from app.services.agent import executor as agent_executor
from app.services.agent import memory as agent_memory
from app.services.agent import planner as agent_planner
from app.services.agent import router as agent_router
from app.services.chat_intent import tool_choice_for_round
from app.services.subtitle_store import get_record, infer_source, list_record_ids_in_folder
from app.services.folder_store import get_folder, is_uncategorized_folder_id

SYSTEM_PROMPT = """你是笔记分析助手。用户会引用本地库中的 B 站字幕或小红书笔记作为上下文。
请优先基于引用笔记回答；若引用不足以回答，可结合常识并说明依据。
回答使用 Markdown，代码用 fenced code block。简洁准确。

你还可通过工具操作本地笔记库（查看、分类、提取链接、移动、删除、导出）。
需要实际改动库数据或拉取新笔记时调用工具；纯分析/问答时直接回答。
查未分类笔记时优先 list_records(folder_name="未分类", include_text=true)；get_record 必须带 id 或 ids。"""

# ponytail: 单条引用最多字符，避免撑爆上下文
REF_CHAR_LIMIT = 12000
# ponytail: 分类引用合计上限；超出则截断并标注
FOLDER_REF_TOTAL_CHAR_LIMIT = 48000
_MAX_TOOL_ROUNDS = 5
# ponytail: 非 stream LLM 回复分块大小，保持前端流式体验
_DELTA_CHUNK_SIZE = 48

_http_client: httpx.AsyncClient | None = None


def _openai_http_client() -> httpx.AsyncClient:
    """绕过 NO_PROXY 含 ::1 时 httpx 误解析为端口 :1 的问题。"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(120.0))
    return _http_client


def _normalize_base_url(url: str) -> str:
    return (url or "").strip().rstrip("/") or "https://api.openai.com/v1"


def _llm_client() -> tuple[AsyncOpenAI, str]:
    api_key = settings_store.get_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "未配置 OpenAI API Key，请在「设置」页填写，或在 backend/.env 设置 OPENAI_API_KEY"
        )
    base_url = _normalize_base_url(settings_store.get_openai_base_url())
    model = settings_store.get_openai_model()
    return (
        AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=_openai_http_client(),
        ),
        model,
    )


def _folder_display_name(folder_id: str) -> str:
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


def _uncategorized_query_block(user_message: str) -> str:
    """未分类查询时预加载正文，避免模型空参 get_record。"""
    if "未分类" not in user_message:
        return ""
    result = chat_tools.execute(
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
    """从最近对话文本提取 12 位笔记 id（如 #7368ee9aac7f）。"""
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


def _last_list_record_ids(messages: list[dict[str, Any]], *, uncategorized_only: bool = False) -> list[str]:
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
            parsed = json.loads(
                chat_tools.execute("list_records", {"folder_name": "未分类", "limit": 50})
            )
            return [str(r.get("id") or "").strip() for r in parsed.get("records") or [] if r.get("id")]
        except json.JSONDecodeError:
            pass
    return []


def _repair_tool_args(
    tool_name: str,
    args: dict[str, Any],
    messages: list[dict[str, Any]],
    user_message: str,
) -> dict[str, Any]:
    """ponytail: 模型空参时从 list_records 结果或对话 id 回填。"""
    if tool_name == "get_record":
        if chat_tools._record_id(args) or chat_tools._record_ids(args):
            return args
        uncat = "未分类" in user_message
        ids = _last_list_record_ids(messages, uncategorized_only=uncat)
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


def build_messages(
    history: list[dict[str, str]],
    user_message: str,
    reference_record_ids: list[str],
    reference_folder_ids: list[str] | None = None,
    *,
    query_mode: bool = False,
) -> list[dict[str, Any]]:
    ref_ids = [x for x in reference_record_ids if x]
    folder_ids = [x for x in (reference_folder_ids or []) if x]

    ref_block = _build_reference_block(ref_ids)
    folder_block = _build_folder_reference_block(folder_ids, summary_only=query_mode)
    system = SYSTEM_PROMPT
    blocks = [b for b in (ref_block, folder_block) if b]
    if query_mode and "未分类" in user_message:
        uncat_block = _uncategorized_query_block(user_message)
        if uncat_block:
            blocks.append(uncat_block)
    if blocks:
        system = f"{SYSTEM_PROMPT}\n\n" + "\n\n".join(blocks)

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in history:
        role = m.get("role")
        if role == "tools":
            continue
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": m.get("content") or ""})
    messages.append({"role": "user", "content": user_message})
    return messages


def _tool_step_dict(name: str) -> dict[str, str]:
    cat = chat_tools.tool_category(name)
    return {
        "name": name,
        "label": chat_tools.tool_label(name),
        "category_label": chat_tools.TOOL_CATEGORIES.get(cat, {}).get("label", ""),
    }


def _tool_sse_start(name: str) -> dict[str, str]:
    meta = _tool_step_dict(name)
    return {
        "name": meta["name"],
        "label": meta["label"],
        "category": chat_tools.tool_category(name),
        "category_label": meta["category_label"],
    }


def _tool_preview(result: str) -> str:
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            if parsed.get("error"):
                return str(parsed["error"])[:120]
            if parsed.get("title"):
                return str(parsed["title"])[:120]
            if parsed.get("count") is not None:
                return f"count={parsed['count']}"
            moved = parsed.get("moved")
            if isinstance(moved, list) and moved:
                bc = parsed.get("batch_count")
                if bc:
                    return f"moved={len(moved)}, batches={bc}"
                return f"moved={len(moved)}"
    except json.JSONDecodeError:
        pass
    return (result or "")[:120]


def _tool_ok(result: str) -> bool:
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            if parsed.get("ok") is False:
                return False
            if parsed.get("error"):
                return False
    except json.JSONDecodeError:
        pass
    return True


def _yield_text_deltas(text: str, chunk_size: int = _DELTA_CHUNK_SIZE):
    """非 stream LLM 全文回复时分块 yield delta SSE。"""
    if not text:
        return
    for i in range(0, len(text), chunk_size):
        yield f"data: {json.dumps({'delta': text[i : i + chunk_size]}, ensure_ascii=False)}\n\n"


async def _stream_execute_plan(
    client: AsyncOpenAI,
    model: str,
    thread_id: str,
    user_message: str,
    history: list[dict[str, Any]],
    ref_ids: list[str],
    folder_ids: list[str],
    plan: dict[str, Any],
) -> AsyncIterator[str]:
    """Executor + LLM 汇报。"""
    exec_steps, summary = agent_executor.run_plan(plan)
    tool_steps: list[dict[str, Any]] = []
    for step in exec_steps:
        name = step["name"]
        meta = _tool_step_dict(name)
        ok = bool(step.get("ok", True))
        preview = str(step.get("preview") or "")
        yield f"data: {json.dumps({'tool_start': _tool_sse_start(name)}, ensure_ascii=False)}\n\n"
        tool_steps.append({**meta, "ok": ok, "preview": preview, "status": "done"})
        yield f"data: {json.dumps({'tool_end': {'name': name, 'ok': ok, 'preview': preview}}, ensure_ascii=False)}\n\n"

    messages = build_messages(history, user_message, ref_ids, folder_ids)
    messages.append(
        {
            "role": "user",
            "content": agent_planner.execution_hint(plan, summary),
        }
    )
    full = ""
    stream = await client.chat.completions.create(model=model, messages=messages, stream=True)
    async for event in stream:
        choice = event.choices[0] if event.choices else None
        if not choice:
            continue
        piece = choice.delta.content or ""
        if piece:
            full += piece
            yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
    if not full.strip():
        moved = summary.get("records_moved", 0)
        full = f"已执行方案，成功移动 {moved} 条笔记。"
        yield f"data: {json.dumps({'delta': full}, ensure_ascii=False)}\n\n"
    chat_store.append_turn(thread_id, user_message, full, tool_steps or None)
    agent_memory.clear_pending(thread_id)
    yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"


async def _stream_present_plan(
    client: AsyncOpenAI,
    model: str,
    thread_id: str,
    user_message: str,
    history: list[dict[str, Any]],
    ref_ids: list[str],
    folder_ids: list[str],
    plan: dict[str, Any],
) -> AsyncIterator[str]:
    """展示 Plan，等待用户确认。"""
    messages = build_messages(history, user_message, ref_ids, folder_ids)
    messages.append(
        {
            "role": "user",
            "content": (
                f"{agent_planner.presentation_hint(plan)}\n\n"
                f"方案 JSON：\n```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```"
            ),
        }
    )
    full = ""
    stream = await client.chat.completions.create(model=model, messages=messages, stream=True)
    async for event in stream:
        choice = event.choices[0] if event.choices else None
        if not choice:
            continue
        piece = choice.delta.content or ""
        if piece:
            full += piece
            yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
    if not full.strip():
        full = "已生成变更方案；确认后可执行。"
        yield f"data: {json.dumps({'delta': full}, ensure_ascii=False)}\n\n"
    agent_memory.save_pending(thread_id, plan)
    chat_store.append_turn(thread_id, user_message, full, None)
    yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"


async def _stream_query_tools(
    client: AsyncOpenAI,
    model: str,
    thread_id: str,
    user_message: str,
    history: list[dict[str, Any]],
    ref_ids: list[str],
    folder_ids: list[str],
) -> AsyncIterator[str]:
    """Query 路径：只读工具循环。"""
    messages = build_messages(history, user_message, ref_ids, folder_ids, query_mode=True)
    tools = chat_tools.get_openai_tools(intent="query")
    full = ""
    tool_steps: list[dict[str, Any]] = []

    for round_idx in range(_MAX_TOOL_ROUNDS):
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice_for_round("query", round_idx),
            stream=False,
        )
        msg = response.choices[0].message
        if not msg.tool_calls:
            if msg.content:
                full = msg.content
            break

        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            fn = tc.function
            tool_name = fn.name or ""
            try:
                args = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            args = _repair_tool_args(tool_name, args, messages, user_message)
            yield f"data: {json.dumps({'tool_start': _tool_sse_start(tool_name)}, ensure_ascii=False)}\n\n"
            result = chat_tools.execute(tool_name, args)
            ok = _tool_ok(result)
            preview = _tool_preview(result)
            meta = _tool_step_dict(tool_name)
            tool_steps.append({**meta, "ok": ok, "preview": preview, "status": "done"})
            yield f"data: {json.dumps({'tool_end': {'name': tool_name, 'ok': ok, 'preview': preview}}, ensure_ascii=False)}\n\n"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    if not full.strip():
        stream = await client.chat.completions.create(
            model=model, messages=messages, tools=tools, tool_choice="none", stream=True
        )
        async for event in stream:
            choice = event.choices[0] if event.choices else None
            if not choice:
                continue
            piece = choice.delta.content or ""
            if piece:
                full += piece
                yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
    else:
        for chunk in _yield_text_deltas(full):
            yield chunk

    if not full.strip():
        full = "（模型未返回内容。）"
        yield f"data: {json.dumps({'delta': full}, ensure_ascii=False)}\n\n"
    chat_store.append_turn(thread_id, user_message, full, tool_steps or None)
    yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"


async def _stream_read(
    client: AsyncOpenAI,
    model: str,
    thread_id: str,
    user_message: str,
    history: list[dict[str, Any]],
    ref_ids: list[str],
    folder_ids: list[str],
) -> AsyncIterator[str]:
    """Read 路径：纯对话，不调工具。"""
    messages = build_messages(history, user_message, ref_ids, folder_ids)
    full = ""
    stream = await client.chat.completions.create(model=model, messages=messages, stream=True)
    async for event in stream:
        choice = event.choices[0] if event.choices else None
        if not choice:
            continue
        piece = choice.delta.content or ""
        if piece:
            full += piece
            yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
    if not full.strip():
        full = "（模型未返回内容。）"
        yield f"data: {json.dumps({'delta': full}, ensure_ascii=False)}\n\n"
    chat_store.append_turn(thread_id, user_message, full, None)
    yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"


async def sse_chat_stream(
    thread_id: str,
    message: str,
    reference_record_ids: list[str] | None = None,
    reference_folder_ids: list[str] | None = None,
) -> AsyncIterator[str]:
    """
    通用 Agent 流水线：Router → Planner → (Confirm?) → Executor → Summarize。
    """
    user_message = (message or "").strip()
    if not user_message:
        yield f"data: {json.dumps({'error': '消息不能为空'}, ensure_ascii=False)}\n\n"
        return

    ref_ids = [x for x in (reference_record_ids or []) if x]
    folder_ids = [x for x in (reference_folder_ids or []) if x]
    try:
        history = chat_store.get_messages(thread_id)
        client, model = _llm_client()
        mem = agent_memory.load(thread_id)
        pending = mem.get("pending_plan")

        route = await agent_router.route(
            client,
            model,
            user_message,
            history,
            pending_plan=pending if isinstance(pending, dict) else None,
            awaiting_confirmation=mem.get("awaiting_confirmation", False),
            reference_record_ids=ref_ids,
            reference_folder_ids=folder_ids,
        )

        if route.kind == "confirm":
            plan = agent_planner.plan_for_confirm(
                pending if isinstance(pending, dict) else None,
                history,
                user_message,
            )
            if plan and plan.get("steps"):
                async for chunk in _stream_execute_plan(
                    client, model, thread_id, user_message, history, ref_ids, folder_ids, plan
                ):
                    yield chunk
                return
            # 无 plan 时降级为 mutate 重新规划
            route = RouteDecision(kind="mutate", mutate_goal="generic", auto_execute=True)

        if route.kind == "cancel":
            agent_memory.clear_pending(thread_id)
            reply = "已取消待确认方案。"
            chat_store.append_turn(thread_id, user_message, reply, None)
            yield f"data: {json.dumps({'delta': reply}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        if route.is_mutate:
            plan = await agent_planner.plan_mutate(
                client,
                model,
                user_message,
                history,
                mutate_goal=route.mutate_goal,
                auto_execute=route.auto_execute,
                ref_ids=ref_ids,
                folder_ids=folder_ids,
            )
            if plan.get("requires_confirmation") and plan.get("steps"):
                async for chunk in _stream_present_plan(
                    client, model, thread_id, user_message, history, ref_ids, folder_ids, plan
                ):
                    yield chunk
                return
            if plan.get("steps"):
                async for chunk in _stream_execute_plan(
                    client, model, thread_id, user_message, history, ref_ids, folder_ids, plan
                ):
                    yield chunk
                return
            # 无步骤：展示 meta 说明
            async for chunk in _stream_present_plan(
                client, model, thread_id, user_message, history, ref_ids, folder_ids, plan
            ):
                yield chunk
            return

        if route.kind == "query":
            async for chunk in _stream_query_tools(
                client, model, thread_id, user_message, history, ref_ids, folder_ids
            ):
                yield chunk
            return

        async for chunk in _stream_read(
            client, model, thread_id, user_message, history, ref_ids, folder_ids
        ):
            yield chunk

    except Exception as err:  # noqa: BLE001
        yield f"data: {json.dumps({'error': str(err)}, ensure_ascii=False)}\n\n"
