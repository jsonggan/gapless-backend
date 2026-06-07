"""LLM endpoints."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.api.deps import CurrentActiveUserDep
from app.core.config import settings
from app.schemas.llm import ChatRequest
from app.services.llm import get_llm_service, to_lc_messages

router = APIRouter()


async def _stream_chat(request: ChatRequest) -> EventSourceResponse:
    """Stream chat completion using SSE."""
    if not settings.KIMI_API_KEY:
        raise HTTPException(status_code=503, detail="LLM service is not configured")

    service = get_llm_service()
    lc_messages = to_lc_messages(request.messages)

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        async for chunk in service.stream_chat(lc_messages):
            yield {"data": json.dumps({"delta": chunk, "done": False})}
        yield {"data": json.dumps({"delta": "", "done": True})}

    return EventSourceResponse(event_generator())


@router.post("/chat")
async def chat_stream(
    current_user: CurrentActiveUserDep,
    request: ChatRequest,
) -> EventSourceResponse:
    """Authenticated streaming chat endpoint."""
    return await _stream_chat(request)
