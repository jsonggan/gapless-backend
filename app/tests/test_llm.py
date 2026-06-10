"""Tests for LLM endpoints."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage

from app.schemas.llm import ChatMessage
from app.services import llm as llm_module
from app.services.llm import LLMService, build_chat_model, get_llm_service, to_lc_messages


class _FakeStreamingClient:
    """Small async streaming client used by LLMService unit tests."""

    def __init__(self, chunks: list[object]) -> None:
        self._chunks = chunks

    def astream(self, messages: object) -> AsyncIterator[object]:
        async def gen() -> AsyncIterator[object]:
            for chunk in self._chunks:
                yield chunk

        return gen()


class TestLLMService:
    """Tests for LLM service helpers."""

    def test_to_lc_messages_converts_roles(self) -> None:
        messages = [
            ChatMessage(role="system", content="Rules"),
            ChatMessage(role="assistant", content="Prior answer"),
            ChatMessage(role="user", content="Question"),
        ]

        converted = to_lc_messages(messages)

        assert isinstance(converted[0], SystemMessage)
        assert converted[0].content == "Rules"
        assert isinstance(converted[1], AIMessage)
        assert converted[1].content == "Prior answer"
        assert isinstance(converted[2], HumanMessage)
        assert converted[2].content == "Question"

    def test_build_chat_model_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", None)

        with pytest.raises(RuntimeError, match="KIMI_API_KEY"):
            build_chat_model()

    def test_build_chat_model_uses_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")
        monkeypatch.setattr("app.core.config.settings.KIMI_MODEL", "fake-model")
        monkeypatch.setattr("app.core.config.settings.KIMI_BASE_URL", "https://example.test/v1")

        with patch("app.services.llm.ChatOpenAI") as chat_openai:
            model = build_chat_model(streaming=False)

        assert model is chat_openai.return_value
        chat_openai.assert_called_once_with(
            model="fake-model",
            api_key="fake-key",
            base_url="https://example.test/v1",
            streaming=False,
        )

    def test_build_chat_model_json_mode_and_max_tokens(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")
        monkeypatch.setattr("app.core.config.settings.KIMI_MODEL", "fake-model")
        monkeypatch.setattr("app.core.config.settings.KIMI_BASE_URL", "https://example.test/v1")

        with patch("app.services.llm.ChatOpenAI") as chat_openai:
            build_chat_model(streaming=False, max_tokens=4096, json_mode=True)

        chat_openai.assert_called_once_with(
            model="fake-model",
            api_key="fake-key",
            base_url="https://example.test/v1",
            streaming=False,
            extra_body={"max_tokens": 4096},
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    @pytest.mark.asyncio
    async def test_stream_chat_yields_text_chunks_only(self) -> None:
        client = _FakeStreamingClient(
            [
                AIMessageChunk(content="Hello"),
                "ignored",
                AIMessageChunk(content=""),
                AIMessageChunk(content=" world"),
            ]
        )
        with patch("app.services.llm.build_chat_model", return_value=client):
            service = LLMService()

        chunks = [chunk async for chunk in service.stream_chat([HumanMessage(content="Hi")])]

        assert chunks == ["Hello", " world"]

    def test_get_llm_service_caches_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm_module, "_llm_service", None)
        client = _FakeStreamingClient([])
        with patch("app.services.llm.build_chat_model", return_value=client):
            first = get_llm_service()
            second = get_llm_service()

        assert first is second


class TestLLMChat:
    """Tests for the LLM chat streaming endpoint."""

    @pytest.mark.asyncio
    async def test_chat_stream_authenticated(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test authenticated streaming chat."""
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter(["Hello, ", "world!"])

        mock_service = MagicMock()
        mock_service.stream_chat = lambda *args, **kwargs: mock_stream
        with patch(
            "app.api.v1.endpoints.llm.get_llm_service",
            return_value=mock_service,
        ):
            response = await auth_client.post(
                "/api/v1/llm/chat",
                json={"messages": [{"role": "user", "content": "Hi"}]},
            )
            assert response.status_code == 200
            text = response.text
            assert "Hello, " in text
            assert "world!" in text
            assert '"done": true' in text

    @pytest.mark.asyncio
    async def test_chat_stream_unauthenticated(self, client: AsyncClient) -> None:
        """Test unauthenticated chat request fails."""
        response = await client.post(
            "/api/v1/llm/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_stream_not_configured(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test chat when LLM is not configured returns 503."""
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", None)
        response = await auth_client.post(
            "/api/v1/llm/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 503
