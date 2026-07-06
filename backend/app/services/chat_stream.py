"""OpenAI 兼容 SSE 对话（可引用本地库记录 + 内置工具）。"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.services import chat_store, chat_tools, settings_store
from app.services.subtitle_store import get_record, infer_source

SYSTEM_PROMPT = """你是笔记分析助手。用户会引用本地库中的 B 站字幕或小红书笔记作为上下文。
请优先基于引用笔记回答；若引用不足以回答，可结合常识并说明依据。
回答使用 Markdown，代码用 fenced code block。简洁准确。

你还可通过工具操作本地笔记库（查看、分类、提取链接、移动、删除、导出）。
需要实际改动库数据或拉取新笔记时调用工具；纯分析/问答时直接回答。"""

# ponytail: 单条引用最多字符，避免撑爆上下文
REF_CHAR_LIMIT = 12000
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
) -> list[dict[str, Any]]:
    ref_block = _build_reference_block(reference_record_ids)
    system = SYSTEM_PROMPT
    if ref_block:
        system = f"{SYSTEM_PROMPT}\n\n{ref_block}"

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


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
) -> AsyncIterator[str]:
    user_message = (message or "").strip()
    if not user_message:
        yield f"data: {json.dumps({'error': '消息不能为空'}, ensure_ascii=False)}\n\n"
        return

    ref_ids = [x for x in (reference_record_ids or []) if x]
    try:
        history = chat_store.get_messages(thread_id)
        messages = build_messages(history, user_message, ref_ids)
        client, model = _llm_client()
        tools = chat_tools.get_openai_tools()
        full = ""

        for _round in range(_MAX_TOOL_ROUNDS):
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
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

                yield f"data: {json.dumps({'tool_start': {'name': tool_name, 'label': chat_tools.tool_label(tool_name), 'category': chat_tools.tool_category(tool_name), 'category_label': chat_tools.TOOL_CATEGORIES.get(chat_tools.tool_category(tool_name), {}).get('label', '')}}, ensure_ascii=False)}\n\n"

                result = chat_tools.execute(tool_name, args)
                ok = _tool_ok(result)
                yield f"data: {json.dumps({'tool_end': {'name': tool_name, 'ok': ok, 'preview': _tool_preview(result)}}, ensure_ascii=False)}\n\n"

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

        chat_store.append_exchange(thread_id, user_message, full)
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
    except Exception as err:  # noqa: BLE001
        yield f"data: {json.dumps({'error': str(err)}, ensure_ascii=False)}\n\n"
