"""Tests for LLM endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


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
