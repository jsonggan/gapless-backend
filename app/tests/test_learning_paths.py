"""Tests for learning path platform-style endpoints."""

from typing import cast
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import user as user_crud
from app.models.learning_path import (
    LearningPath,
    LearningPathFeedbackAttempt,
    LearningPathLessonBlock,
    LearningPathModule,
)
from app.models.user import User
from app.schemas.learning_path import LearningPathFeedbackResponse
from app.schemas.user import UserCreate
from app.services.learning_feedback import (
    LearningFeedbackGenerationError,
    _generate_learning_path_feedback,
    _parse_feedback_payload,
)


class _FakeFeedbackModel:
    """Small async model stub used by feedback service tests."""

    def __init__(self, reply: AIMessage) -> None:
        self.reply = reply

    async def ainvoke(self, messages: object) -> AIMessage:
        return self.reply


def _feedback_response(feedback: str | None = None) -> LearningPathFeedbackResponse:
    return LearningPathFeedbackResponse(
        feedback=feedback
        or "You correctly identified retrieval as the source of grounding context.",
        strengths=["Names grounding context as the key benefit."],
        improvements=["Mention that retrieved documents should support the final answer."],
        suggested_answer=(
            "Retrieval adds relevant source context before generation so the answer can be "
            "grounded in documents instead of only model memory."
        ),
    )


async def _create_learning_path(
    db: AsyncSession,
    *,
    user_id: int,
    title: str = "Practical RAG",
) -> LearningPath:
    path = LearningPath(
        user_id=user_id,
        topic="teach me RAG",
        title=title,
        summary="A focused path for building retrieval augmented generation systems.",
        modules=[
            LearningPathModule(
                order=1,
                title="Retrieval Foundations",
                learning_objective="Explain why retrieval improves generation.",
                estimated_minutes=12,
                blocks=[
                    LearningPathLessonBlock(
                        order=1,
                        block_type="markdown",
                        content={
                            "markdown": "Retrieval supplies grounding context before generation."
                        },
                    ),
                    LearningPathLessonBlock(
                        order=2,
                        block_type="process",
                        content={
                            "title": "Answer with retrieval",
                            "steps": [
                                {
                                    "title": "Search",
                                    "description": "Find the matching documents.",
                                },
                                {
                                    "title": "Generate",
                                    "description": "Answer from the retrieved context.",
                                },
                            ],
                        },
                    ),
                    LearningPathLessonBlock(
                        order=3,
                        block_type="single_choice_question",
                        content={
                            "question": "What does retrieval add to generation?",
                            "options": [
                                "Grounding context",
                                "More parameters",
                                "Faster decoding",
                            ],
                            "correct_option_index": 0,
                            "explanation": "Retrieval supplies source material to answer from.",
                        },
                    ),
                ],
            ),
            LearningPathModule(
                order=2,
                title="Chunking Strategy",
                learning_objective="Choose chunks that preserve useful context.",
                estimated_minutes=15,
                blocks=[
                    LearningPathLessonBlock(
                        order=1,
                        block_type="markdown",
                        content={"markdown": "Chunk size controls precision, recall, and context."},
                    ),
                    LearningPathLessonBlock(
                        order=2,
                        block_type="reflection_review",
                        content={
                            "prompt": "Draft a chunking rule for one technical document.",
                            "review_criteria": [
                                "Your chunks have stable boundaries.",
                                "Your chunks can answer likely questions.",
                            ],
                        },
                    ),
                ],
            ),
        ],
    )
    db.add(path)
    await db.commit()
    return path


class TestLearningPathFeedbackService:
    """Tests for free-text answer feedback helpers."""

    def test_parse_feedback_payload_validates_json(self) -> None:
        parsed = _parse_feedback_payload(
            """
            ```json
            {
              "feedback": "Good start: you connected retrieval with grounding.",
              "strengths": ["Identifies the purpose of retrieval."],
              "improvements": ["Add that retrieved evidence should support the answer."],
              "suggested_answer": "Retrieval supplies relevant source material so generation can answer from evidence."
            }
            ```
            """,
        )

        assert parsed.feedback.startswith("Good start")
        assert parsed.strengths == ["Identifies the purpose of retrieval."]
        assert parsed.improvements == ["Add that retrieved evidence should support the answer."]

    def test_parse_feedback_payload_rejects_bad_shape(self) -> None:
        with pytest.raises(LearningFeedbackGenerationError, match="feedback schema"):
            _parse_feedback_payload('{"feedback": ""}')

    @pytest.mark.asyncio
    async def test_generate_feedback_rejects_truncated_reply(self) -> None:
        model = _FakeFeedbackModel(
            AIMessage(content="{}", response_metadata={"finish_reason": "length"})
        )

        with pytest.raises(LearningFeedbackGenerationError, match="truncated"):
            await _generate_learning_path_feedback(
                cast(ChatOpenAI, model),
                context="Retrieval supplies grounding context.",
                question="What does retrieval add?",
                answer="Grounding.",
            )


class TestLearningPaths:
    """Tests for learning path library, detail, and progress APIs."""

    @pytest.mark.asyncio
    async def test_titles_and_list_include_only_current_users_progress(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
    ) -> None:
        path = await _create_learning_path(db, user_id=test_user.id)
        other_user = await user_crud.create(
            db,
            UserCreate(
                email="other@example.com",
                username="otheruser",
                password="password123",
            ),
        )
        await _create_learning_path(db, user_id=other_user.id, title="Other User Path")

        first_module = path.modules[0]
        mark_response = await auth_client.post(
            f"/api/v1/learning-paths/{path.id}/modules/{first_module.id}/read"
        )
        assert mark_response.status_code == 200

        title_response = await auth_client.get("/api/v1/learning-paths/titles")

        assert title_response.status_code == 200
        titles = title_response.json()
        assert titles == [
            {
                "id": path.id,
                "title": "Practical RAG",
                "topic": "teach me RAG",
                "progress_percent": 50,
                "is_completed": False,
                "updated_at": titles[0]["updated_at"],
            }
        ]

        list_response = await auth_client.get("/api/v1/learning-paths/")

        assert list_response.status_code == 200
        paths = list_response.json()
        assert len(paths) == 1
        assert paths[0]["id"] == path.id
        assert paths[0]["estimated_minutes"] == 27
        assert paths[0]["total_modules"] == 2
        assert paths[0]["read_modules"] == 1
        assert paths[0]["next_module_id"] == path.modules[1].id

    @pytest.mark.asyncio
    async def test_detail_mark_read_and_mark_unread(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
    ) -> None:
        path = await _create_learning_path(db, user_id=test_user.id)
        first_module = path.modules[0]
        second_module = path.modules[1]

        detail_response = await auth_client.get(f"/api/v1/learning-paths/{path.id}")

        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["progress"]["progress_percent"] == 0
        assert [module["is_read"] for module in detail["modules"]] == [False, False]
        assert [block["type"] for block in detail["modules"][0]["blocks"]] == [
            "markdown",
            "process",
            "single_choice_question",
        ]
        assert detail["modules"][0]["blocks"][0]["id"] == first_module.blocks[0].id
        assert detail["modules"][0]["blocks"][0]["order"] == 1
        assert detail["modules"][0]["blocks"][0] == {
            "id": first_module.blocks[0].id,
            "order": 1,
            "type": "markdown",
            "markdown": "Retrieval supplies grounding context before generation.",
        }
        assert detail["modules"][0]["blocks"][2]["correct_option_index"] == 0
        assert [block["type"] for block in detail["modules"][1]["blocks"]] == [
            "markdown",
            "reflection_review",
        ]
        assert detail["modules"][1]["blocks"][1]["review_criteria"] == [
            "Your chunks have stable boundaries.",
            "Your chunks can answer likely questions.",
        ]

        progress_response = await auth_client.patch(
            f"/api/v1/learning-paths/{path.id}/modules/{first_module.id}/progress",
            json={"is_read": True},
        )

        assert progress_response.status_code == 200
        progress = progress_response.json()
        assert progress["module_id"] == first_module.id
        assert progress["is_read"] is True
        assert progress["read_at"] is not None
        assert progress["progress"]["read_modules"] == 1
        assert progress["progress"]["progress_percent"] == 50
        assert progress["progress"]["next_module_id"] == second_module.id

        complete_response = await auth_client.post(
            f"/api/v1/learning-paths/{path.id}/modules/{second_module.id}/read"
        )

        assert complete_response.status_code == 200
        complete = complete_response.json()
        assert complete["progress"]["is_completed"] is True
        assert complete["progress"]["progress_percent"] == 100
        assert complete["progress"]["next_module_id"] is None

        unread_response = await auth_client.delete(
            f"/api/v1/learning-paths/{path.id}/modules/{first_module.id}/read"
        )

        assert unread_response.status_code == 200
        unread = unread_response.json()
        assert unread["is_read"] is False
        assert unread["read_at"] is None
        assert unread["progress"]["read_modules"] == 1
        assert unread["progress"]["progress_percent"] == 50
        assert unread["progress"]["next_module_id"] == first_module.id

    @pytest.mark.asyncio
    async def test_history_returns_stats_recent_paths_and_activity(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
    ) -> None:
        first_path = await _create_learning_path(db, user_id=test_user.id)
        second_path = await _create_learning_path(
            db,
            user_id=test_user.id,
            title="Prompt Engineering",
        )
        other_user = await user_crud.create(
            db,
            UserCreate(
                email="other@example.com",
                username="otheruser",
                password="password123",
            ),
        )
        await _create_learning_path(db, user_id=other_user.id, title="Other User Path")

        for module in second_path.modules:
            response = await auth_client.post(
                f"/api/v1/learning-paths/{second_path.id}/modules/{module.id}/read"
            )
            assert response.status_code == 200
        response = await auth_client.post(
            f"/api/v1/learning-paths/{first_path.id}/modules/{first_path.modules[0].id}/read"
        )
        assert response.status_code == 200

        history_response = await auth_client.get("/api/v1/learning-paths/history")

        assert history_response.status_code == 200
        history = history_response.json()
        assert history["stats"] == {
            "total_paths": 2,
            "completed_paths": 1,
            "in_progress_paths": 1,
            "total_modules": 4,
            "read_modules": 3,
            "minutes_read": 39,
        }

        recent_path_ids = [path["id"] for path in history["recent_paths"]]
        assert set(recent_path_ids) == {first_path.id, second_path.id}
        recent_by_id = {path["id"]: path for path in history["recent_paths"]}
        assert recent_by_id[second_path.id]["is_completed"] is True
        assert recent_by_id[first_path.id]["progress_percent"] == 50

        activity = history["recent_activity"]
        assert len(activity) == 3
        assert activity[0]["learning_path_id"] == first_path.id
        assert activity[0]["module_title"] == "Retrieval Foundations"
        assert all(item["read_at"] is not None for item in activity)
        assert {item["learning_path_id"] for item in activity} == {
            first_path.id,
            second_path.id,
        }

    @pytest.mark.asyncio
    async def test_history_is_empty_for_new_user(
        self,
        auth_client: AsyncClient,
    ) -> None:
        response = await auth_client.get("/api/v1/learning-paths/history")

        assert response.status_code == 200
        history = response.json()
        assert history["stats"] == {
            "total_paths": 0,
            "completed_paths": 0,
            "in_progress_paths": 0,
            "total_modules": 0,
            "read_modules": 0,
            "minutes_read": 0,
        }
        assert history["recent_paths"] == []
        assert history["recent_activity"] == []

    @pytest.mark.asyncio
    async def test_history_respects_limits(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
    ) -> None:
        path = await _create_learning_path(db, user_id=test_user.id)
        await _create_learning_path(db, user_id=test_user.id, title="Second Path")
        for module in path.modules:
            response = await auth_client.post(
                f"/api/v1/learning-paths/{path.id}/modules/{module.id}/read"
            )
            assert response.status_code == 200

        response = await auth_client.get(
            "/api/v1/learning-paths/history",
            params={"recent_paths_limit": 1, "recent_activity_limit": 1},
        )

        assert response.status_code == 200
        history = response.json()
        assert history["stats"]["total_paths"] == 2
        assert len(history["recent_paths"]) == 1
        assert len(history["recent_activity"]) == 1
        assert history["recent_activity"][0]["module_title"] == "Chunking Strategy"

    @pytest.mark.asyncio
    async def test_progress_endpoints_enforce_learning_path_ownership(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
    ) -> None:
        path = await _create_learning_path(db, user_id=test_user.id)
        other_user = await user_crud.create(
            db,
            UserCreate(
                email="owner@example.com",
                username="owneruser",
                password="password123",
            ),
        )
        other_path = await _create_learning_path(
            db,
            user_id=other_user.id,
            title="Private Path",
        )

        other_path_response = await auth_client.post(
            f"/api/v1/learning-paths/{other_path.id}/modules/{other_path.modules[0].id}/read"
        )
        wrong_module_response = await auth_client.post(
            f"/api/v1/learning-paths/{path.id}/modules/{other_path.modules[0].id}/read"
        )

        assert other_path_response.status_code == 404
        assert wrong_module_response.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_feedback_authenticated(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = await _create_learning_path(db, user_id=test_user.id)
        first_module = path.modules[0]
        first_block = first_module.blocks[0]
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")

        with patch(
            "app.api.v1.endpoints.learning_paths.generate_learning_path_feedback",
            return_value=_feedback_response(),
        ) as generate_feedback:
            response = await auth_client.post(
                (
                    f"/api/v1/learning-paths/{path.id}/modules/{first_module.id}"
                    f"/blocks/{first_block.id}/feedback"
                ),
                json={
                    "context": "Retrieval supplies grounding context before generation.",
                    "question": "What does retrieval add to generation?",
                    "answer": "It gives grounding context.",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["learning_path_id"] == path.id
        assert data["module_id"] == first_module.id
        assert data["lesson_block_id"] == first_block.id
        assert data["question"] == "What does retrieval add to generation?"
        assert data["answer"] == "It gives grounding context."
        assert data["ai_response"]["feedback"].startswith("You correctly identified retrieval")
        assert data["ai_response"]["strengths"] == ["Names grounding context as the key benefit."]
        assert data["ai_response"]["improvements"] == [
            "Mention that retrieved documents should support the final answer."
        ]
        assert data["created_at"] is not None
        generate_feedback.assert_awaited_once_with(
            context="Retrieval supplies grounding context before generation.",
            question="What does retrieval add to generation?",
            answer="It gives grounding context.",
        )

        attempts = (
            await db.execute(
                select(LearningPathFeedbackAttempt).where(
                    LearningPathFeedbackAttempt.user_id == test_user.id,
                    LearningPathFeedbackAttempt.lesson_block_id == first_block.id,
                )
            )
        ).scalars()
        assert len(list(attempts)) == 1

    @pytest.mark.asyncio
    async def test_feedback_latest_returns_only_newest_attempt(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = await _create_learning_path(db, user_id=test_user.id)
        first_module = path.modules[0]
        first_block = first_module.blocks[0]
        url = (
            f"/api/v1/learning-paths/{path.id}/modules/{first_module.id}"
            f"/blocks/{first_block.id}/feedback"
        )
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")

        with patch(
            "app.api.v1.endpoints.learning_paths.generate_learning_path_feedback",
            side_effect=[
                _feedback_response("First feedback."),
                _feedback_response("Second feedback."),
            ],
        ):
            first_response = await auth_client.post(
                url,
                json={
                    "context": "Retrieval supplies grounding context before generation.",
                    "question": "What does retrieval add to generation?",
                    "answer": "It searches.",
                },
            )
            second_response = await auth_client.post(
                url,
                json={
                    "context": "Retrieval supplies grounding context before generation.",
                    "question": "What does retrieval add to generation?",
                    "answer": "It adds grounding documents.",
                },
            )

        latest_response = await auth_client.get(f"{url}/latest")

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert latest_response.status_code == 200
        latest = latest_response.json()
        assert latest["id"] == second_response.json()["id"]
        assert latest["answer"] == "It adds grounding documents."
        assert latest["ai_response"]["feedback"] == "Second feedback."

        attempts = (
            await db.execute(
                select(LearningPathFeedbackAttempt).where(
                    LearningPathFeedbackAttempt.user_id == test_user.id,
                    LearningPathFeedbackAttempt.lesson_block_id == first_block.id,
                )
            )
        ).scalars()
        assert len(list(attempts)) == 2

    @pytest.mark.asyncio
    async def test_generate_feedback_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/learning-paths/1/modules/1/blocks/1/feedback",
            json={
                "context": "Retrieval supplies grounding context before generation.",
                "question": "What does retrieval add to generation?",
                "answer": "It gives grounding context.",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_generate_feedback_not_configured(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = await _create_learning_path(db, user_id=test_user.id)
        first_module = path.modules[0]
        first_block = first_module.blocks[0]
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", None)

        response = await auth_client.post(
            (
                f"/api/v1/learning-paths/{path.id}/modules/{first_module.id}"
                f"/blocks/{first_block.id}/feedback"
            ),
            json={
                "context": "Retrieval supplies grounding context before generation.",
                "question": "What does retrieval add to generation?",
                "answer": "It gives grounding context.",
            },
        )

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_generate_feedback_invalid_llm_response(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = await _create_learning_path(db, user_id=test_user.id)
        first_module = path.modules[0]
        first_block = first_module.blocks[0]
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")

        with patch(
            "app.api.v1.endpoints.learning_paths.generate_learning_path_feedback",
            side_effect=LearningFeedbackGenerationError("bad shape"),
        ):
            response = await auth_client.post(
                (
                    f"/api/v1/learning-paths/{path.id}/modules/{first_module.id}"
                    f"/blocks/{first_block.id}/feedback"
                ),
                json={
                    "context": "Retrieval supplies grounding context before generation.",
                    "question": "What does retrieval add to generation?",
                    "answer": "It gives grounding context.",
                },
            )

        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_feedback_endpoints_enforce_block_ownership(
        self,
        auth_client: AsyncClient,
        db: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = await _create_learning_path(db, user_id=test_user.id)
        other_user = await user_crud.create(
            db,
            UserCreate(
                email="feedback-owner@example.com",
                username="feedbackowner",
                password="password123",
            ),
        )
        other_path = await _create_learning_path(db, user_id=other_user.id, title="Private Path")
        monkeypatch.setattr("app.core.config.settings.KIMI_API_KEY", "fake-key")

        wrong_owner_response = await auth_client.post(
            (
                f"/api/v1/learning-paths/{other_path.id}/modules/{other_path.modules[0].id}"
                f"/blocks/{other_path.modules[0].blocks[0].id}/feedback"
            ),
            json={
                "context": "Private context.",
                "question": "Private question?",
                "answer": "Private answer.",
            },
        )
        wrong_block_response = await auth_client.get(

                f"/api/v1/learning-paths/{path.id}/modules/{path.modules[0].id}"
                f"/blocks/{other_path.modules[0].blocks[0].id}/feedback/latest"

        )

        assert wrong_owner_response.status_code == 404
        assert wrong_block_response.status_code == 404
