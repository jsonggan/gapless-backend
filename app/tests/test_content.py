"""Tests for the content generation service and endpoint."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage

from app.schemas.content import ContentResponse, ContentSection
from app.services.content import _parse_outline, generate_content


class _FakeModel:
    """Fake chat model: the 1st ``ainvoke`` returns the outline, the rest bodies.

    ``generate_content`` always awaits the outline call before fanning out to the
    per-section calls, so ordering by ``call_count`` is reliable.
    """

    def __init__(self, outline_text: str) -> None:
        self._outline_text = outline_text
        self.call_count = 0

    async def ainvoke(self, messages: list) -> AIMessage:
        self.call_count += 1
        if self.call_count == 1:
            return AIMessage(content=self._outline_text)
        # Echo the section prompt so per-section content can be asserted.
        return AIMessage(content=f"Body for: {messages[-1].content}")


class TestParseOutline:
    """Tests for outline parsing."""

    def test_strips_list_markers_and_blanks(self) -> None:
        text = "1. Intro\n2) Basics\n- Why it matters\n* Details\n#Heading\n\nPlain"
        assert _parse_outline(text) == [
            "Intro",
            "Basics",
            "Why it matters",
            "Details",
            "Heading",
            "Plain",
        ]

    def test_caps_number_of_sections(self) -> None:
        text = "\n".join(f"Section {i}" for i in range(20))
        assert len(_parse_outline(text)) == 7


class TestGenerateContent:
    """Tests for the content generation service (model mocked)."""

    @pytest.mark.asyncio
    async def test_builds_outline_and_sections(self) -> None:
        model = _FakeModel("Intro\nWhat is RAG\nWhy it matters")
        with patch("app.services.content.build_chat_model", return_value=model):
            result = await generate_content("teach me RAG")

        assert result.topic == "teach me RAG"
        assert [s.title for s in result.sections] == ["Intro", "What is RAG", "Why it matters"]
        assert all(s.content.startswith("Body for:") for s in result.sections)
        # One outline call + one call per section.
        assert model.call_count == 4

    @pytest.mark.asyncio
    async def test_empty_outline_yields_no_sections(self) -> None:
        model = _FakeModel("")
        with patch("app.services.content.build_chat_model", return_value=model):
            result = await generate_content("teach me nothing")

        assert result.sections == []
        assert model.call_count == 1


class TestContentEndpoint:
    """Tests for the content generation endpoint."""

    @pytest.mark.asyncio
    async def test_generate_authenticated(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")

        async def fake_generate(topic: str) -> ContentResponse:
            return ContentResponse(
                topic=topic,
                sections=[ContentSection(title="Intro", content="Hello.")],
            )

        with patch("app.api.v1.endpoints.content.generate_content", fake_generate):
            response = await auth_client.post(
                "/api/v1/content/generate",
                json={"topic": "teach me RAG"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["topic"] == "teach me RAG"
        assert body["sections"] == [{"title": "Intro", "content": "Hello."}]

    @pytest.mark.asyncio
    async def test_generate_unauthenticated(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/content/generate",
            json={"topic": "teach me RAG"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_generate_not_configured(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", None)
        response = await auth_client.post(
            "/api/v1/content/generate",
            json={"topic": "teach me RAG"},
        )
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_generate_rejects_empty_topic(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")
        response = await auth_client.post(
            "/api/v1/content/generate",
            json={"topic": ""},
        )
        assert response.status_code == 422
