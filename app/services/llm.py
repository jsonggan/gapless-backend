"""LLM provider helpers and chat service.

This module centralises construction of the chat model so that both the plain
chat endpoint and the agent runner share a single, configurable entry point.
As the agent system grows, prefer adding new providers/models behind
``build_chat_model`` rather than instantiating clients directly elsewhere.
"""

from collections.abc import AsyncIterator, Iterable

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


def build_chat_model(*, streaming: bool = True) -> ChatOpenAI:
    """Build a configured chat model client.

    Args:
        streaming: Whether the client should stream tokens.

    Returns:
        A configured ``ChatOpenAI`` instance pointed at the Kimi endpoint.

    Raises:
        RuntimeError: If the API key is not configured.
    """
    api_key = settings.KIMI_API_KEY
    if not api_key:
        raise RuntimeError("KIMI_API_KEY is not configured")
    return ChatOpenAI(
        model=settings.KIMI_MODEL,
        api_key=api_key,  # type: ignore[arg-type]
        base_url=settings.KIMI_BASE_URL,
        streaming=streaming,
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
