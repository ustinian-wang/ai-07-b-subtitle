"""OpenAI 兼容 SSE 对话（可引用本地库记录 + 内置工具）。"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.services import chat_store, chat_tools, settings_store
from app.services.chat_classify_plan import (
    apply_classify_plan,
    build_classify_plan,
    build_classify_plan_block,
    classify_plan_hint,
    execution_summary,
    plan_actionable_work,
    resolve_classify_refs,
)
from app.services.chat_intent import TurnIntent, infer_turn_intent, tool_choice_for_round
from app.services.subtitle_store import get_record, infer_source, list_record_ids_in_folder
from app.services.folder_store import get_folder, is_uncategorized_folder_id

SYSTEM_PROMPT = """你是笔记分析助手。用户会引用本地库中的 B 站字幕或小红书笔记作为上下文。
请优先基于引用笔记回答；若引用不足以回答，可结合常识并说明依据。
回答使用 Markdown，代码用 fenced code block。简洁准确。

你还可通过工具操作本地笔记库（查看、分类、提取链接、移动、删除、导出）。
需要实际改动库数据或拉取新笔记时调用工具；纯分析/问答时直接回答。"""

# ponytail: 单条引用最多字符，避免撑爆上下文
REF_CHAR_LIMIT = 12000
# ponytail: 分类引用合计上限；超出则截断并标注
FOLDER_REF_TOTAL_CHAR_LIMIT = 48000
_MAX_TOOL_ROUNDS = 5

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


def build_messages(
    history: list[dict[str, str]],
    user_message: str,
    reference_record_ids: list[str],
    reference_folder_ids: list[str] | None = None,
    *,
    turn: TurnIntent | None = None,
) -> list[dict[str, Any]]:
    ref_ids = [x for x in reference_record_ids if x]
    folder_ids = [x for x in (reference_folder_ids or []) if x]
    eff_ref_ids, eff_folder_ids = ref_ids, folder_ids
    if turn and turn.is_classify:
        eff_ref_ids, eff_folder_ids = resolve_classify_refs(ref_ids, folder_ids, history)

    ref_block = _build_reference_block(ref_ids)
    folder_block = _build_folder_reference_block(
        eff_folder_ids if (turn and turn.is_classify) else folder_ids,
        summary_only=bool(turn and turn.is_classify),
    )
    system = SYSTEM_PROMPT
    blocks = [b for b in (ref_block, folder_block) if b]
    if turn and turn.is_classify:
        plan_block = build_classify_plan_block(eff_ref_ids, eff_folder_ids, history)
        if plan_block:
            blocks.append(plan_block)
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


async def sse_chat_stream(
    thread_id: str,
    message: str,
    reference_record_ids: list[str] | None = None,
    reference_folder_ids: list[str] | None = None,
) -> AsyncIterator[str]:
    user_message = (message or "").strip()
    if not user_message:
        yield f"data: {json.dumps({'error': '消息不能为空'}, ensure_ascii=False)}\n\n"
        return

    ref_ids = [x for x in (reference_record_ids or []) if x]
    folder_ids = [x for x in (reference_folder_ids or []) if x]
    try:
        history = chat_store.get_messages(thread_id)
        client, model = _llm_client()
        hint = classify_plan_hint(ref_ids, folder_ids, history)
        turn = await infer_turn_intent(
            client,
            model,
            user_message,
            history,
            reference_record_ids=ref_ids,
            reference_folder_ids=folder_ids,
            classify_hint=hint,
        )
        messages = build_messages(history, user_message, ref_ids, folder_ids, turn=turn)
        full = ""
        tool_steps: list[dict[str, Any]] = []

        # ponytail: 分类编排 — LLM 判 execute_tools，服务端执行 create/move
        if turn.is_classify:
            eff_ref_ids, eff_folder_ids = resolve_classify_refs(ref_ids, folder_ids, history)
            plan = build_classify_plan(eff_ref_ids, eff_folder_ids, history)
            actionable = plan_actionable_work(plan)

            if turn.execute_tools:
                steps, plan = apply_classify_plan(eff_ref_ids, eff_folder_ids, history)
                for step in steps:
                    name = step["name"]
                    meta = _tool_step_dict(name)
                    yield f"data: {json.dumps({'tool_start': _tool_sse_start(name)}, ensure_ascii=False)}\n\n"
                    ok = bool(step.get("ok", True))
                    preview = str(step.get("preview") or "")
                    tool_steps.append({**meta, "ok": ok, "preview": preview, "status": "done"})
                    yield f"data: {json.dumps({'tool_end': {'name': name, 'ok': ok, 'preview': preview}}, ensure_ascii=False)}\n\n"

                summary = execution_summary(steps, plan)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"系统已按预分析完成工具调用，结果 JSON：\n{summary}\n"
                            f"跳过合集 {len(plan.get('skip_collection') or [])} 条，"
                            f"未识别 {len(plan.get('skip_unknown') or [])} 条。"
                            "请用 Markdown 简要汇报：新建了哪些文件夹、移动了多少条、哪些保留未分类。"
                        ),
                    }
                )
            else:
                hint_msg = "请基于上方预分析输出分类方案（Markdown 表格），本轮不要调用任何工具。"
                if not actionable["has_work"]:
                    hint_msg += "当前引用范围内无需新建文件夹或移动笔记，请直接说明现状。"
                else:
                    hint_msg += "用户若确认执行，可回复要求落库。"
                messages.append({"role": "user", "content": hint_msg})

            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
            async for event in stream:
                choice = event.choices[0] if event.choices else None
                if not choice:
                    continue
                piece = choice.delta.content or ""
                if piece:
                    full += piece
                    yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
            if not full.strip():
                if turn.execute_tools:
                    full = "已完成分类工具调用。"
                elif actionable["has_work"]:
                    full = "已生成分类方案；确认后可要求执行落库。"
                else:
                    full = "当前引用范围内没有需要移动的笔记，分类已是最新状态。"
                yield f"data: {json.dumps({'delta': full}, ensure_ascii=False)}\n\n"
            chat_store.append_turn(thread_id, user_message, full, tool_steps or None)
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        intent = turn.tool_intent
        tools = chat_tools.get_openai_tools(intent=intent)

        for round_idx in range(_MAX_TOOL_ROUNDS):
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice_for_round(intent, round_idx),
                stream=False,
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                if msg.content:
                    full = msg.content
                # ponytail: write 首轮未调工具则补编排 user 消息，促发 create/move
                if intent == "write" and round_idx == 0 and turn.execute_tools:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": full or "（未调用工具。）",
                        }
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "请按预分析清单调用工具完成笔记库变更："
                                "先 list_folders，再 create_folder 补缺失文件夹，"
                                "最后用 move_records 移动可单城笔记；合集笔记跳过。"
                                "完成后简要汇报移动条数。"
                            ),
                        }
                    )
                    full = ""
                    continue
                break

            messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                fn = tc.function
                tool_name = fn.name or ""
                try:
                    args = json.loads(fn.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                yield f"data: {json.dumps({'tool_start': _tool_sse_start(tool_name)}, ensure_ascii=False)}\n\n"

                result = chat_tools.execute(tool_name, args)
                ok = _tool_ok(result)
                preview = _tool_preview(result)
                meta = _tool_step_dict(tool_name)
                tool_steps.append({**meta, "ok": ok, "preview": preview, "status": "done"})
                yield f"data: {json.dumps({'tool_end': {'name': tool_name, 'ok': ok, 'preview': preview}}, ensure_ascii=False)}\n\n"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

        if not full.strip():
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="none",
                stream=True,
            )
            async for event in stream:
                choice = event.choices[0] if event.choices else None
                if not choice:
                    continue
                piece = choice.delta.content or ""
                if piece:
                    full += piece
                    yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
        elif full.strip():
            chunk_size = 48
            for i in range(0, len(full), chunk_size):
                piece = full[i : i + chunk_size]
                yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"

        if not full.strip():
            full = "（模型未返回内容；若需操作笔记库，请确认模型支持 function calling。）"
            yield f"data: {json.dumps({'delta': full}, ensure_ascii=False)}\n\n"

        chat_store.append_turn(thread_id, user_message, full, tool_steps or None)
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
    except Exception as err:  # noqa: BLE001
        yield f"data: {json.dumps({'error': str(err)}, ensure_ascii=False)}\n\n"
