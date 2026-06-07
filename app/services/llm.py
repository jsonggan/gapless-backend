"""LLM service using LangChain with Kimi (OpenAI-compatible)."""

from collections.abc import AsyncIterator

from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings


class LLMService:
    """Service for interacting with the Kimi LLM via LangChain."""

    def __init__(self) -> None:
        api_key = settings.KIMI_API_KEY
        if not api_key:
            raise RuntimeError("KIMI_API_KEY is not configured")
        self._client = ChatOpenAI(
            model=settings.KIMI_MODEL,
            api_key=api_key,  # type: ignore[arg-type]
            base_url=settings.KIMI_BASE_URL,
            streaming=True,
        )

    async def stream_chat(
        self,
        messages: list[BaseMessage],
    ) -> AsyncIterator[str]:
        """Stream an LLM chat completion."""
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
