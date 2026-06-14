"""Tests for content generation endpoints."""

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.learning_path import LearningPath, LearningPathModule
from app.models.user import User
from app.schemas.content import (
    ContentModule,
    ContentResponse,
    MarkdownBlock,
    ProcessBlock,
    ProcessStep,
    ReflectionReviewBlock,
    SingleChoiceQuestionBlock,
)
from app.services.content import _parse_content_payload


def _content_response() -> ContentResponse:
    return ContentResponse(
        topic="teach me RAG",
        title="Practical RAG",
        summary="A focused path for building retrieval augmented generation systems.",
        modules=[
            ContentModule(
                order=1,
                title="Retrieval Foundations",
                learning_objective="Explain why retrieval improves generation.",
                estimated_minutes=12,
                blocks=[
                    MarkdownBlock(
                        markdown="Retrieval supplies grounding context before generation.",
                    ),
                    ProcessBlock(
                        title="Answer with retrieval",
                        steps=[
                            ProcessStep(
                                title="Search",
                                description="Find the matching documents.",
                            ),
                            ProcessStep(
                                title="Generate",
                                description="Answer from the retrieved context.",
                            ),
                        ],
                    ),
                    SingleChoiceQuestionBlock(
                        question="What does retrieval add to generation?",
                        options=[
                            "Grounding context",
                            "More parameters",
                            "Faster decoding",
                        ],
                        correct_option_index=0,
                        explanation="Retrieval supplies source material to answer from.",
                    ),
                ],
            ),
            ContentModule(
                order=2,
                title="Chunking Strategy",
                learning_objective="Choose chunks that preserve useful context.",
                estimated_minutes=15,
                blocks=[
                    MarkdownBlock(
                        markdown="Chunk size controls precision, recall, and context.",
                    ),
                    ReflectionReviewBlock(
                        prompt="Draft a chunking rule for one technical document.",
                        review_criteria=[
                            "Your chunks have stable boundaries.",
                            "Your chunks can answer likely questions.",
                        ],
                    ),
                ],
            ),
        ],
    )


class TestContentService:
    """Tests for content parsing helpers."""

    def test_parse_content_payload_allows_code_fences_inside_markdown(self) -> None:
        payload = {
            "title": "Production RAG Systems",
            "summary": "A practical path for production retrieval systems.",
            "modules": [
                {
                    "order": 1,
                    "title": "Retrieval Architecture",
                    "learning_objective": "Design a production RAG retrieval flow.",
                    "estimated_minutes": 18,
                    "blocks": [
                        {
                            "type": "markdown",
                            "markdown": (
                                "## Hybrid retrieval\n\n"
                                "```python\n"
                                "async def retrieve(query: str):\n"
                                "    return await vector_search(query)\n"
                                "```"
                            ),
                        },
                        {
                            "type": "process",
                            "title": "Deploy retrieval",
                            "steps": [
                                {
                                    "title": "Index documents",
                                    "description": "Store chunks and metadata.",
                                },
                                {
                                    "title": "Query documents",
                                    "description": "Retrieve the most relevant chunks.",
                                },
                            ],
                        },
                        {
                            "type": "single_choice_question",
                            "question": "What does hybrid retrieval combine?",
                            "options": [
                                "Sparse and dense search",
                                "Two LLM prompts",
                                "Only cached answers",
                            ],
                            "correct_option_index": 0,
                            "explanation": "Hybrid retrieval combines exact and semantic matching.",
                        },
                    ],
                }
            ],
        }

        parsed = _parse_content_payload("production RAG", json.dumps(payload))

        assert parsed.title == "Production RAG Systems"
        assert parsed.modules[0].blocks[0].type == "markdown"
        assert "```python" in parsed.modules[0].blocks[0].markdown


class TestContentGenerate:
    """Tests for generated learning content persistence."""

    @pytest.mark.asyncio
    async def test_generate_saves_learning_path(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")

        with patch(
            "app.api.v1.endpoints.content.generate_content",
            return_value=_content_response(),
        ):
            response = await auth_client.post(
                "/api/v1/content/generate",
                json={"topic": "teach me RAG"},
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["id"], int)
        assert data["topic"] == "teach me RAG"
        assert [module["order"] for module in data["modules"]] == [1, 2]
        assert all(isinstance(module["id"], int) for module in data["modules"])
        assert [block["type"] for block in data["modules"][0]["blocks"]] == [
            "markdown",
            "process",
            "single_choice_question",
        ]
        assert [block["type"] for block in data["modules"][1]["blocks"]] == [
            "markdown",
            "reflection_review",
        ]

        result = await db.execute(
            select(LearningPath)
            .options(selectinload(LearningPath.modules).selectinload(LearningPathModule.blocks))
            .where(LearningPath.id == data["id"])
        )
        learning_path = result.scalar_one()

        assert learning_path.user_id == test_user.id
        assert learning_path.title == "Practical RAG"
        assert [module.title for module in learning_path.modules] == [
            "Retrieval Foundations",
            "Chunking Strategy",
        ]
        first_blocks = learning_path.modules[0].blocks
        assert [block.block_type for block in first_blocks] == [
            "markdown",
            "process",
            "single_choice_question",
        ]
        assert first_blocks[0].content == {
            "markdown": "Retrieval supplies grounding context before generation."
        }
        assert first_blocks[2].content["correct_option_index"] == 0

    @pytest.mark.asyncio
    async def test_generate_not_configured(
        self,
        auth_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", None)

        response = await auth_client.post(
            "/api/v1/content/generate",
            json={"topic": "teach me RAG"},
        )

        assert response.status_code == 503
