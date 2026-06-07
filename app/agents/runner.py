"""Agent execution runner.

Implements a manual tool-calling loop on top of LangChain's ``bind_tools``:

    1. Stream a model turn, forwarding text tokens to the caller.
    2. If the model requested tool calls, execute each and feed the results
       back into the conversation.
    3. Repeat until the model answers without tool calls (or we hit the
       iteration cap).

This keeps full control over orchestration, which is the foundation for the
more complex multi-step / multi-agent behaviour to come.
"""

from collections.abc import AsyncIterator, Sequence

from langchain_core.messages import AIMessageChunk, BaseMessage, ToolMessage

from app.agents.tools import get_tool, get_tools
from app.schemas.agent import AgentEvent
from app.services.llm import build_chat_model

# Safety cap so a misbehaving model cannot loop on tool calls forever.
DEFAULT_MAX_ITERATIONS = 8


async def stream_agent(
    messages: Sequence[BaseMessage],
    *,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> AsyncIterator[AgentEvent]:
    """Run the agent loop, yielding events as they happen.

    Args:
        messages: The starting conversation.
        max_iterations: Maximum number of model turns before giving up.

    Yields:
        ``AgentEvent`` items describing tokens, tool calls, results, and
        completion.
    """
    tools = get_tools()
    model = build_chat_model(streaming=True).bind_tools(tools)
    conversation: list[BaseMessage] = list(messages)

    for _ in range(max_iterations):
        gathered: AIMessageChunk | None = None
        async for chunk in model.astream(conversation):
            if not isinstance(chunk, AIMessageChunk):
                continue
            if isinstance(chunk.content, str) and chunk.content:
                yield AgentEvent(type="token", delta=chunk.content)
            gathered = chunk if gathered is None else gathered + chunk

        if gathered is None:
            break

        conversation.append(gathered)

        if not gathered.tool_calls:
            yield AgentEvent(type="done")
            return

        for call in gathered.tool_calls:
            name = call["name"]
            args = call["args"]
            call_id = call.get("id") or name
            yield AgentEvent(type="tool_call", tool=name, args=args)

            result = await _execute_tool(name, args)
            yield AgentEvent(type="tool_result", tool=name, result=result)
            conversation.append(ToolMessage(content=result, tool_call_id=call_id))

    # Reached the iteration cap without a final, tool-free answer.
    yield AgentEvent(type="done")


async def _execute_tool(name: str, args: dict[str, object]) -> str:
    """Execute a registered tool by name, returning its result as text."""
    tool = get_tool(name)
    if tool is None:
        return f"Error: unknown tool '{name}'"
    try:
        return str(await tool.ainvoke(args))
    except Exception as exc:  # noqa: BLE001 - surface tool errors back to the model
        return f"Error executing tool '{name}': {exc}"
