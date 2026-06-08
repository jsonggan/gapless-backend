"""Learning path CRUD operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning_path import LearningPath, LearningPathModule
from app.schemas.content import ContentResponse


class CRUDLearningPath:
    """CRUD operations for generated learning paths."""

    async def create_from_content(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        content: ContentResponse,
    ) -> LearningPath:
        """Persist generated content as a learning path and ordered modules."""
        db_obj = LearningPath(
            user_id=user_id,
            topic=content.topic,
            title=content.title,
            summary=content.summary,
            modules=[
                LearningPathModule(
                    order=module.order,
                    title=module.title,
                    learning_objective=module.learning_objective,
                    estimated_minutes=module.estimated_minutes,
                    explanation=module.explanation,
                    key_points=module.key_points,
                    example=module.example,
                    practice_prompt=module.practice_prompt,
                    success_criteria=module.success_criteria,
                )
                for module in content.modules
            ],
        )
        db.add(db_obj)
        await db.commit()
        return db_obj


learning_path = CRUDLearningPath()
