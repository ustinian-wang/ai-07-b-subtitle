"""OpenAI 兼容 SSE 对话：薄入口，编排委托 runtime.Pipeline。"""
from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from openai import AsyncOpenAI

from app.runtime.context import RunContext
from app.runtime.events import StepEvent
from app.runtime.pipeline import default_pipeline
from app.runtime.sse import event_to_sse
from app.services import chat_store, settings_store
from app.services.agent import memory as agent_memory

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


async def sse_chat_stream(
    thread_id: str,
    message: str,
    reference_record_ids: list[str] | None = None,
    reference_folder_ids: list[str] | None = None,
) -> AsyncIterator[str]:
    """
    通用 Agent 流水线：load ctx → Pipeline.run → map events to SSE JSON。
    API 契约不变：delta / tool_start / tool_end / done / error。
    """
    user_message = (message or "").strip()
    ref_ids = [x for x in (reference_record_ids or []) if x]
    folder_ids = [x for x in (reference_folder_ids or []) if x]

    if not user_message:
        yield event_to_sse(StepEvent.error("消息不能为空"))
        return

    try:
        history = chat_store.get_messages(thread_id)
        client, model = _llm_client()
        mem = agent_memory.load(thread_id)
        ctx = RunContext(
            thread_id=thread_id,
            user_message=user_message,
            history=history,
            ref_ids=ref_ids,
            folder_ids=folder_ids,
            client=client,
            model=model,
            registry=default_pipeline.registry,
            plugins=default_pipeline.plugins,
            mem=mem,
        )
        async for event in default_pipeline.run(ctx):
            yield event_to_sse(event)
    except Exception as err:  # noqa: BLE001
        yield event_to_sse(StepEvent.error(str(err)))


def _self_check() -> None:
    assert _normalize_base_url("") == "https://api.openai.com/v1"


if __name__ == "__main__":
    _self_check()
    print("chat_stream ok")
