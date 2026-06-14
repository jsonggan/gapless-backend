"""Tests for assessment generation endpoints and service helpers."""

from typing import cast
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from app.schemas.assessment import (
    AssessmentOption,
    AssessmentResponse,
    MultipleChoiceAssessmentQuestion,
    SingleChoiceAssessmentQuestion,
)
from app.services.assessment import (
    AssessmentGenerationError,
    _generate_assessment,
    _parse_assessment_payload,
)


def _assessment_response() -> AssessmentResponse:
    return AssessmentResponse(
        topic="teach me RAG",
        title="RAG readiness check",
        instructions="Answer honestly so the lesson can match your current depth.",
        questions=[
            SingleChoiceAssessmentQuestion(
                id="q1",
                prompt="How familiar are you with RAG?",
                options=[
                    AssessmentOption(id="a", text="I have only heard the term."),
                    AssessmentOption(id="b", text="I know the high-level flow."),
                    AssessmentOption(id="c", text="I have built a basic RAG pipeline."),
                ],
            ),
            MultipleChoiceAssessmentQuestion(
                id="q2",
                prompt="Which pieces have you used?",
                options=[
                    AssessmentOption(id="a", text="Chunking"),
                    AssessmentOption(id="b", text="Embeddings"),
                    AssessmentOption(id="c", text="Vector search"),
                ],
                max_selections=3,
            ),
            SingleChoiceAssessmentQuestion(
                id="q3",
                prompt="What level should the first lesson assume?",
                options=[
                    AssessmentOption(id="a", text="Start from fundamentals."),
                    AssessmentOption(id="b", text="Skip basics and focus on implementation."),
                ],
            ),
        ],
    )


class _FakeAssessmentModel:
    """Small async model stub used by assessment service tests."""

    def __init__(self, reply: AIMessage) -> None:
        self.reply = reply

    async def ainvoke(self, messages: object) -> AIMessage:
        return self.reply


class TestAssessmentService:
    """Tests for assessment parsing and generation helpers."""

    def test_parse_assessment_payload_validates_json(self) -> None:
        parsed = _parse_assessment_payload(
            "teach me RAG",
            """
            ```json
            {
              "title": "RAG readiness check",
              "instructions": "Pick the closest answer.",
              "questions": [
                {
                  "id": "q1",
                  "type": "single_choice",
                  "prompt": "How familiar are you with retrieval?",
                  "options": [
                    {"id": "a", "text": "New to it"},
                    {"id": "b", "text": "Used it before"}
                  ]
                },
                {
                  "id": "q2",
                  "type": "multiple_choice",
                  "prompt": "What have you used?",
                  "options": [
                    {"id": "a", "text": "Embeddings"},
                    {"id": "b", "text": "Vector search"}
                  ]
                },
                {
                  "id": "q3",
                  "type": "free_text",
                  "prompt": "What do you want to build?",
                  "max_words": 40
                }
              ]
            }
            ```
            """,
        )

        assert parsed.topic == "teach me RAG"
        assert parsed.questions[0].type == "single_choice"
        assert parsed.questions[1].type == "multiple_choice"
        assert parsed.questions[2].type == "free_text"

    def test_parse_assessment_rejects_duplicate_question_ids(self) -> None:
        with pytest.raises(AssessmentGenerationError, match="assessment schema"):
            _parse_assessment_payload(
                "teach me RAG",
                """
                {
                  "title": "RAG readiness check",
                  "instructions": "Pick the closest answer.",
                  "questions": [
                    {
                      "id": "q1",
                      "type": "single_choice",
                      "prompt": "First?",
                      "options": [
                        {"id": "a", "text": "A"},
                        {"id": "b", "text": "B"}
                      ]
                    },
                    {
                      "id": "q1",
                      "type": "single_choice",
                      "prompt": "Second?",
                      "options": [
                        {"id": "a", "text": "A"},
                        {"id": "b", "text": "B"}
                      ]
                    },
                    {
                      "id": "q3",
                      "type": "single_choice",
                      "prompt": "Third?",
                      "options": [
                        {"id": "a", "text": "A"},
                        {"id": "b", "text": "B"}
                      ]
                    }
                  ]
                }
                """,
            )

    @pytest.mark.asyncio
    async def test_generate_assessment_rejects_truncated_reply(self) -> None:
        model = _FakeAssessmentModel(
            AIMessage(content="{}", response_metadata={"finish_reason": "length"})
        )

        with pytest.raises(AssessmentGenerationError, match="truncated"):
            await _generate_assessment(cast(ChatOpenAI, model), "teach me RAG", question_count=6)


class TestAssessmentGenerate:
    """Tests for generated assessment endpoint."""

    @pytest.mark.asyncio
    async def test_generate_assessment_authenticated(
        self,
        auth_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")

        with patch(
            "app.api.v1.endpoints.assessments.generate_assessment",
            return_value=_assessment_response(),
        ):
            response = await auth_client.post(
                "/api/v1/assessments/generate",
                json={"topic": "teach me RAG"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "teach me RAG"
        assert data["title"] == "RAG readiness check"
        assert [question["type"] for question in data["questions"]] == [
            "single_choice",
            "multiple_choice",
            "single_choice",
        ]
        assert data["questions"][0]["options"][0] == {
            "id": "a",
            "text": "I have only heard the term.",
        }

    @pytest.mark.asyncio
    async def test_generate_assessment_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/assessments/generate",
            json={"topic": "teach me RAG"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_generate_assessment_not_configured(
        self,
        auth_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", None)

        response = await auth_client.post(
            "/api/v1/assessments/generate",
            json={"topic": "teach me RAG"},
        )

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_generate_assessment_invalid_llm_response(
        self,
        auth_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")

        with patch(
            "app.api.v1.endpoints.assessments.generate_assessment",
            side_effect=AssessmentGenerationError("bad shape"),
        ):
            response = await auth_client.post(
                "/api/v1/assessments/generate",
                json={"topic": "teach me RAG"},
            )

        assert response.status_code == 502
