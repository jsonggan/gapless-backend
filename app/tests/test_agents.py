"""Tests for the agent layer: tools, registry, runner, and endpoint."""

from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessageChunk, HumanMessage

from app.agents.runner import _execute_tool, stream_agent
from app.agents.tools import get_tool, get_tools, register
from app.agents.tools.math import add
from app.schemas.agent import AgentEvent


class TestAddTool:
    """Tests for the ``add`` math tool."""

    @pytest.mark.asyncio
    async def test_add_returns_sum(self) -> None:
        assert await add.ainvoke({"a": 2, "b": 3}) == 5
        assert await add.ainvoke({"a": -1.5, "b": 0.5}) == -1.0

    def test_add_metadata(self) -> None:
        assert add.name == "add"
        assert "add" in add.description.lower()


class TestRegistry:
    """Tests for the tool registry."""

    def test_add_is_registered(self) -> None:
        names = {tool.name for tool in get_tools()}
        assert "add" in names

    def test_get_tool_by_name(self) -> None:
        assert get_tool("add") is add
        assert get_tool("does-not-exist") is None

    def test_register_is_idempotent(self) -> None:
        before = len(get_tools())
        register(add)  # already present
        assert len(get_tools()) == before


class TestExecuteTool:
    """Tests for the tool execution helper."""

    @pytest.mark.asyncio
    async def test_execute_known_tool(self) -> None:
        assert await _execute_tool("add", {"a": 1, "b": 2}) == "3.0"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self) -> None:
        result = await _execute_tool("nope", {})
        assert "unknown tool" in result

    @pytest.mark.asyncio
    async def test_execute_tool_error_is_caught(self) -> None:
        # Missing required args -> tool raises -> error surfaced as text.
        result = await _execute_tool("add", {"a": 1})
        assert result.startswith("Error executing tool 'add'")


class _FakeModel:
    """A fake bound chat model whose ``astream`` replays scripted chunks."""

    def __init__(self, turns: list[list[AIMessageChunk]]) -> None:
        self._turns = turns
        self.call_count = 0

    def bind_tools(self, tools: object) -> "_FakeModel":
        return self

    def astream(self, messages: object) -> AsyncIterator[AIMessageChunk]:
        chunks = self._turns[self.call_count]
        self.call_count += 1

        async def gen() -> AsyncIterator[AIMessageChunk]:
            for chunk in chunks:
                yield chunk

        return gen()


async def _collect(messages: list[HumanMessage]) -> list[AgentEvent]:
    return [event async for event in stream_agent(messages)]


class TestRunner:
    """Tests for the agent runner loop (model mocked, real tools)."""

    @pytest.mark.asyncio
    async def test_text_only_run(self) -> None:
        model = _FakeModel([[AIMessageChunk(content="Hi "), AIMessageChunk(content="there")]])
        with patch("app.agents.runner.build_chat_model", return_value=model):
            events = await _collect([HumanMessage(content="hello")])

        types = [e.type for e in events]
        assert types == ["token", "token", "done"]
        assert "".join(e.delta for e in events if e.type == "token") == "Hi there"

    @pytest.mark.asyncio
    async def test_tool_call_run(self) -> None:
        tool_chunk = AIMessageChunk(
            content="",
            tool_call_chunks=[
                {"name": "add", "args": '{"a": 2, "b": 3}', "id": "call_1", "index": 0}
            ],
        )
        model = _FakeModel(
            [
                [tool_chunk],
                [AIMessageChunk(content="The sum is 5.")],
            ]
        )
        with patch("app.agents.runner.build_chat_model", return_value=model):
            events = await _collect([HumanMessage(content="add 2 and 3")])

        by_type = {e.type: e for e in events}
        assert by_type["tool_call"].tool == "add"
        assert by_type["tool_call"].args == {"a": 2, "b": 3}
        assert by_type["tool_result"].result == "5.0"
        assert any(e.type == "token" and "sum is 5" in e.delta for e in events)
        assert events[-1].type == "done"
        assert model.call_count == 2

    @pytest.mark.asyncio
    async def test_iteration_cap(self) -> None:
        def tool_chunk() -> AIMessageChunk:
            return AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {"name": "add", "args": '{"a": 1, "b": 1}', "id": "c", "index": 0}
                ],
            )

        # Model always asks for a tool -> loop should stop at the cap and emit done.
        model = _FakeModel([[tool_chunk()] for _ in range(3)])
        with patch("app.agents.runner.build_chat_model", return_value=model):
            events = [
                e async for e in stream_agent([HumanMessage(content="loop")], max_iterations=3)
            ]

        assert events[-1].type == "done"
        assert model.call_count == 3


class TestAgentEndpoint:
    """Tests for the SSE agent endpoint."""

    @pytest.mark.asyncio
    async def test_run_authenticated(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")

        async def fake_stream(messages: object) -> AsyncIterator[AgentEvent]:
            yield AgentEvent(type="tool_call", tool="add", args={"a": 2, "b": 3})
            yield AgentEvent(type="tool_result", tool="add", result="5.0")
            yield AgentEvent(type="token", delta="The sum is 5.")
            yield AgentEvent(type="done")

        with patch("app.api.v1.endpoints.agents.stream_agent", fake_stream):
            response = await auth_client.post(
                "/api/v1/agents/run",
                json={"messages": [{"role": "user", "content": "add 2 and 3"}]},
            )

        assert response.status_code == 200
        text = response.text
        assert '"tool_call"' in text
        assert '"result":"5.0"' in text
        assert "The sum is 5." in text
        assert '"done"' in text

    @pytest.mark.asyncio
    async def test_run_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/agents/run",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_run_not_configured(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", None)
        response = await auth_client.post(
            "/api/v1/agents/run",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 503
