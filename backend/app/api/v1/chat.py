from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatClearResponse, ChatMessagesResponse, ChatRequest, ChatSessionResponse
from app.services import chat_store
from app.services.chat_stream import sse_chat_stream

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse)
def create_chat_session() -> ChatSessionResponse:
    tid = chat_store.create_thread()
    return ChatSessionResponse(thread_id=tid)


@router.get("/messages", response_model=ChatMessagesResponse)
def get_chat_messages(thread_id: str) -> ChatMessagesResponse:
    return ChatMessagesResponse(
        thread_id=thread_id,
        messages=chat_store.get_messages(thread_id),
    )


@router.delete("/messages", response_model=ChatClearResponse)
def clear_chat_messages(thread_id: str) -> ChatClearResponse:
    chat_store.clear_thread(thread_id)
    return ChatClearResponse(ok=True, thread_id=thread_id)


@router.post("/stream")
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    tid = (body.thread_id or "").strip() or str(uuid.uuid4())
    chat_store.create_thread(tid)
    return StreamingResponse(
        sse_chat_stream(tid, body.message, body.reference_record_ids),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Thread-Id": tid,
        },
    )
