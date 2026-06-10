"""Tests for learning path platform-style endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import user as user_crud
from app.models.learning_path import LearningPath, LearningPathModule
from app.models.user import User
from app.schemas.user import UserCreate


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
                explanation="Retrieval supplies grounding context before generation.",
                key_points=[
                    "Retrieval narrows the source material.",
                    "Generation uses retrieved context to answer.",
                ],
                example="Search product docs, then answer from the matching sections.",
                practice_prompt="List three sources your assistant should retrieve from.",
                success_criteria=[
                    "You can describe retrieval and generation separately.",
                    "You can name a useful source corpus.",
                ],
            ),
            LearningPathModule(
                order=2,
                title="Chunking Strategy",
                learning_objective="Choose chunks that preserve useful context.",
                estimated_minutes=15,
                explanation="Chunk size controls precision, recall, and context quality.",
                key_points=[
                    "Small chunks can lose context.",
                    "Large chunks can dilute relevance.",
                ],
                example="Split an API guide by heading and section boundaries.",
                practice_prompt="Draft a chunking rule for one technical document.",
                success_criteria=[
                    "Your chunks have stable boundaries.",
                    "Your chunks can answer likely questions.",
                ],
            ),
        ],
    )
    db.add(path)
    await db.commit()
    return path


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
