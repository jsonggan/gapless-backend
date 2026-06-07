"""LLM Pydantic schemas."""

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """A single chat message."""

    role: str  # "system", "user", "assistant"
    content: str


class ChatRequest(BaseModel):
    """Chat completion request schema."""

    messages: list[ChatMessage]
    model: str | None = None


class ChatChunk(BaseModel):
    """A single streaming chunk."""

    delta: str
    done: bool = False
