"""LLM provider helpers and chat service.

This module centralises construction of the chat model so the plain chat
endpoint has a single, configurable entry point. Prefer adding new
providers/models behind ``build_chat_model`` rather than instantiating clients
directly elsewhere.
"""

from collections.abc import AsyncIterator, Iterable
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.schemas.llm import ChatMessage


def build_chat_model(
    *,
    streaming: bool = True,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> ChatOpenAI:
    """Build a configured chat model client.

    Args:
        streaming: Whether the client should stream tokens.
        max_tokens: Optional output token cap; ``None`` uses the provider default.
        json_mode: Whether the provider must return a valid JSON object. The
            prompt must still mention JSON for Moonshot to honour it.

    Returns:
        A configured ``ChatOpenAI`` instance pointed at the Kimi endpoint.

    Raises:
        RuntimeError: If the API key is not configured.
    """
    api_key = settings.KIMI_API_KEY
    if not api_key:
        raise RuntimeError("KIMI_API_KEY is not configured")
    extra_kwargs: dict[str, Any] = {}
    if max_tokens is not None:
        # ChatOpenAI rewrites a ``max_tokens`` kwarg to ``max_completion_tokens``,
        # which Moonshot does not document; extra_body sends the classic key as-is.
        extra_kwargs["extra_body"] = {"max_tokens": max_tokens}
    if json_mode:
        extra_kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatOpenAI(
        model=settings.KIMI_MODEL,
        api_key=api_key,  # type: ignore[arg-type]
        base_url=settings.KIMI_BASE_URL,
        streaming=streaming,
        **extra_kwargs,
    )


def to_lc_messages(messages: Iterable[ChatMessage]) -> list[BaseMessage]:
    """Convert API chat messages into LangChain message objects."""
    result: list[BaseMessage] = []
    for msg in messages:
        if msg.role == "system":
            result.append(SystemMessage(content=msg.content))
        elif msg.role == "assistant":
            result.append(AIMessage(content=msg.content))
        else:
            result.append(HumanMessage(content=msg.content))
    return result


class LLMService:
    """Service for plain (tool-free) streaming chat completions."""

    def __init__(self) -> None:
        self._client = build_chat_model(streaming=True)

    async def stream_chat(
        self,
        messages: list[BaseMessage],
    ) -> AsyncIterator[str]:
        """Stream an LLM chat completion as text deltas."""
        async for chunk in self._client.astream(messages):
            if isinstance(chunk, AIMessageChunk):
                text = chunk.content
                if isinstance(text, str) and text:
                    yield text


_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Return the shared LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
