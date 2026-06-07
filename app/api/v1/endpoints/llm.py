"""LLM endpoints."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sse_starlette.sse import EventSourceResponse

from app.api.deps import CurrentActiveUserDep
from app.core.config import settings
from app.schemas.llm import ChatRequest
from app.services.llm import get_llm_service

router = APIRouter()


def _convert_messages(
    messages: list[dict[str, str]],
) -> list[BaseMessage]:
    """Convert plain dict messages to LangChain message objects."""
    result: list[BaseMessage] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
        else:
            result.append(HumanMessage(content=content))
    return result


async def _stream_chat(request: ChatRequest) -> EventSourceResponse:
    """Stream chat completion using SSE."""
    if not settings.KIMI_API_KEY:
        raise HTTPException(status_code=503, detail="LLM service is not configured")

    service = get_llm_service()
    lc_messages = _convert_messages([m.model_dump() for m in request.messages])

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
