"""Agent endpoints."""

from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.agents.runner import stream_agent
from app.api.deps import CurrentActiveUserDep
from app.core.config import settings
from app.schemas.agent import AgentRunRequest
from app.services.llm import to_lc_messages

router = APIRouter()


@router.post("/run")
async def run_agent(
    current_user: CurrentActiveUserDep,
    request: AgentRunRequest,
) -> EventSourceResponse:
    """Run the tool-using agent and stream events over SSE."""
    if not settings.KIMI_API_KEY:
        raise HTTPException(status_code=503, detail="LLM service is not configured")

    messages = to_lc_messages(request.messages)

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        async for event in stream_agent(messages):
            yield {"data": event.model_dump_json()}

    return EventSourceResponse(event_generator())
