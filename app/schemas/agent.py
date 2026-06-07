"""Agent Pydantic schemas."""

from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.llm import ChatMessage


class AgentRunRequest(BaseModel):
    """Request to run the agent over a conversation."""

    messages: list[ChatMessage]


class AgentEvent(BaseModel):
    """A single streamed event from an agent run.

    ``type`` discriminates the payload:
        - ``token``: ``delta`` holds a chunk of the assistant's text.
        - ``tool_call``: the agent invoked ``tool`` with ``args``.
        - ``tool_result``: ``tool`` returned ``result``.
        - ``error``: ``error`` describes what went wrong.
        - ``done``: the run is complete.
    """

    type: Literal["token", "tool_call", "tool_result", "error", "done"]
    delta: str = ""
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: str | None = None
    error: str | None = None
