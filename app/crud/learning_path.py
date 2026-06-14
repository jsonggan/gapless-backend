"""Learning path CRUD operations."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utc_now
from app.models.learning_path import (
    LearningPath,
    LearningPathLessonBlock,
    LearningPathModule,
    LearningPathModuleProgress,
)
from app.models.learning_path import (
    LearningPathFeedbackAttempt as LearningPathFeedbackAttemptModel,
)
from app.schemas.content import (
    ContentModule,
    ContentResponse,
    LessonBlock,
    lesson_block_adapter,
)
from app.schemas.learning_path import (
    LearningHistory,
    LearningHistoryActivity,
    LearningHistoryStats,
    LearningPathDetail,
    LearningPathFeedbackAttempt,
    LearningPathFeedbackRequest,
    LearningPathFeedbackResponse,
    LearningPathModuleProgressResult,
    LearningPathModuleRead,
    LearningPathProgress,
    LearningPathSummary,
    LearningPathTitle,
)


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
                    blocks=[
                        LearningPathLessonBlock(
                            order=index,
                            block_type=block.type,
                            content=block.model_dump(exclude={"id", "order", "type"}),
                        )
                        for index, block in enumerate(module.blocks, start=1)
                    ],
                )
                for module in content.modules
            ],
        )
        db.add(db_obj)
        await db.commit()
        return db_obj

    async def list_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[LearningPath]:
        """List learning paths owned by a user with modules loaded."""
        result = await db.execute(
            select(LearningPath)
            .options(selectinload(LearningPath.modules).selectinload(LearningPathModule.blocks))
            .where(LearningPath.user_id == user_id)
            .order_by(desc(LearningPath.updated_at), desc(LearningPath.id))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        learning_path_id: int,
    ) -> LearningPath | None:
        """Get one user-owned learning path with ordered modules loaded."""
        result = await db.execute(
            select(LearningPath)
            .options(selectinload(LearningPath.modules).selectinload(LearningPathModule.blocks))
            .where(
                LearningPath.id == learning_path_id,
                LearningPath.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def progress_for_paths(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        paths: list[LearningPath],
    ) -> list[LearningPathModuleProgress]:
        """Load read-state rows for the modules in the given paths."""
        module_ids = [module.id for path in paths for module in path.modules]
        if not module_ids:
            return []

        result = await db.execute(
            select(LearningPathModuleProgress).where(
                LearningPathModuleProgress.user_id == user_id,
                LearningPathModuleProgress.module_id.in_(module_ids),
            )
        )
        return list(result.scalars().all())

    async def history_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        recent_paths_limit: int = 5,
        recent_activity_limit: int = 10,
    ) -> LearningHistory:
        """Build the dashboard learning history for a user."""
        result = await db.execute(
            select(LearningPath)
            .options(selectinload(LearningPath.modules).selectinload(LearningPathModule.blocks))
            .where(LearningPath.user_id == user_id)
            .order_by(desc(LearningPath.updated_at), desc(LearningPath.id))
        )
        paths = list(result.scalars().all())
        progress_rows = await self.progress_for_paths(db, user_id=user_id, paths=paths)

        summaries = [self.to_summary(path, progress_rows) for path in paths]
        modules_by_id = {module.id: module for path in paths for module in path.modules}
        read_module_ids = {
            progress.module_id
            for progress in progress_rows
            if progress.is_read and progress.module_id in modules_by_id
        }
        stats = LearningHistoryStats(
            total_paths=len(paths),
            completed_paths=sum(1 for summary in summaries if summary.is_completed),
            in_progress_paths=sum(
                1 for summary in summaries if summary.read_modules > 0 and not summary.is_completed
            ),
            total_modules=len(modules_by_id),
            read_modules=len(read_module_ids),
            minutes_read=sum(
                modules_by_id[module_id].estimated_minutes for module_id in read_module_ids
            ),
        )

        activity_result = await db.execute(
            select(LearningPathModuleProgress, LearningPathModule, LearningPath)
            .join(
                LearningPathModule,
                LearningPathModuleProgress.module_id == LearningPathModule.id,
            )
            .join(LearningPath, LearningPathModule.learning_path_id == LearningPath.id)
            .where(
                LearningPathModuleProgress.user_id == user_id,
                LearningPathModuleProgress.is_read.is_(True),
                LearningPathModuleProgress.read_at.is_not(None),
                LearningPath.user_id == user_id,
            )
            .order_by(desc(LearningPathModuleProgress.read_at))
            .limit(recent_activity_limit)
        )
        recent_activity = [
            LearningHistoryActivity(
                learning_path_id=path.id,
                learning_path_title=path.title,
                module_id=module.id,
                module_title=module.title,
                module_order=module.order,
                read_at=progress.read_at,
            )
            for progress, module, path in activity_result.all()
        ]

        return LearningHistory(
            stats=stats,
            recent_paths=summaries[:recent_paths_limit],
            recent_activity=recent_activity,
        )

    async def set_module_read(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        learning_path_id: int,
        module_id: int,
        is_read: bool,
    ) -> LearningPathModuleProgressResult | None:
        """Set read state for a module in a user-owned learning path."""
        path = await self.get_for_user(
            db,
            user_id=user_id,
            learning_path_id=learning_path_id,
        )
        if path is None:
            return None

        module = next((item for item in path.modules if item.id == module_id), None)
        if module is None:
            return None

        result = await db.execute(
            select(LearningPathModuleProgress).where(
                LearningPathModuleProgress.user_id == user_id,
                LearningPathModuleProgress.module_id == module_id,
            )
        )
        progress_row = result.scalar_one_or_none()
        if progress_row is None:
            progress_row = LearningPathModuleProgress(
                user_id=user_id,
                module_id=module_id,
            )
            db.add(progress_row)

        progress_row.is_read = is_read
        progress_row.read_at = utc_now() if is_read else None

        await db.commit()
        await db.refresh(progress_row)

        progress_rows = await self.progress_for_paths(db, user_id=user_id, paths=[path])
        path_progress = self.to_progress(path, progress_rows)
        return LearningPathModuleProgressResult(
            module_id=module_id,
            is_read=progress_row.is_read,
            read_at=progress_row.read_at,
            progress=path_progress,
        )

    async def get_lesson_block_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        learning_path_id: int,
        module_id: int,
        lesson_block_id: int,
    ) -> LearningPathLessonBlock | None:
        """Get a user-owned lesson block by its full learning path location."""
        result = await db.execute(
            select(LearningPathLessonBlock)
            .join(LearningPathModule, LearningPathLessonBlock.module_id == LearningPathModule.id)
            .join(LearningPath, LearningPathModule.learning_path_id == LearningPath.id)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.id == learning_path_id,
                LearningPathModule.id == module_id,
                LearningPathLessonBlock.id == lesson_block_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_feedback_attempt(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        learning_path_id: int,
        module_id: int,
        lesson_block_id: int,
        request: LearningPathFeedbackRequest,
        ai_response: LearningPathFeedbackResponse,
    ) -> LearningPathFeedbackAttempt:
        """Persist one learner answer and its AI feedback."""
        db_obj = LearningPathFeedbackAttemptModel(
            user_id=user_id,
            learning_path_id=learning_path_id,
            module_id=module_id,
            lesson_block_id=lesson_block_id,
            question=request.question,
            answer=request.answer,
            feedback=ai_response.feedback,
            strengths=ai_response.strengths,
            improvements=ai_response.improvements,
            suggested_answer=ai_response.suggested_answer,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return self.to_feedback_attempt(db_obj)

    async def latest_feedback_attempt(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        learning_path_id: int,
        module_id: int,
        lesson_block_id: int,
    ) -> LearningPathFeedbackAttempt | None:
        """Return the latest saved feedback attempt for one lesson block."""
        result = await db.execute(
            select(LearningPathFeedbackAttemptModel)
            .where(
                LearningPathFeedbackAttemptModel.user_id == user_id,
                LearningPathFeedbackAttemptModel.learning_path_id == learning_path_id,
                LearningPathFeedbackAttemptModel.module_id == module_id,
                LearningPathFeedbackAttemptModel.lesson_block_id == lesson_block_id,
            )
            .order_by(
                desc(LearningPathFeedbackAttemptModel.created_at),
                desc(LearningPathFeedbackAttemptModel.id),
            )
            .limit(1)
        )
        attempt = result.scalar_one_or_none()
        return self.to_feedback_attempt(attempt) if attempt else None

    def to_progress(
        self,
        path: LearningPath,
        progress_rows: list[LearningPathModuleProgress],
    ) -> LearningPathProgress:
        """Compute path progress from loaded modules and read-state rows."""
        read_module_ids = {progress.module_id for progress in progress_rows if progress.is_read}
        total_modules = len(path.modules)
        read_modules = sum(1 for module in path.modules if module.id in read_module_ids)
        progress_percent = round((read_modules / total_modules) * 100) if total_modules else 0
        next_module_id = next(
            (module.id for module in path.modules if module.id not in read_module_ids),
            None,
        )

        return LearningPathProgress(
            total_modules=total_modules,
            read_modules=read_modules,
            progress_percent=progress_percent,
            is_completed=total_modules > 0 and read_modules == total_modules,
            next_module_id=next_module_id,
        )

    def to_title(
        self,
        path: LearningPath,
        progress_rows: list[LearningPathModuleProgress],
    ) -> LearningPathTitle:
        """Build a lightweight title payload for frontend navigation."""
        progress = self.to_progress(path, progress_rows)
        return LearningPathTitle(
            id=path.id,
            title=path.title,
            topic=path.topic,
            progress_percent=progress.progress_percent,
            is_completed=progress.is_completed,
            updated_at=path.updated_at,
        )

    def to_summary(
        self,
        path: LearningPath,
        progress_rows: list[LearningPathModuleProgress],
    ) -> LearningPathSummary:
        """Build a library/list item response for a learning path."""
        progress = self.to_progress(path, progress_rows)
        return LearningPathSummary(
            id=path.id,
            title=path.title,
            topic=path.topic,
            summary=path.summary,
            total_modules=progress.total_modules,
            read_modules=progress.read_modules,
            progress_percent=progress.progress_percent,
            is_completed=progress.is_completed,
            estimated_minutes=self.estimated_minutes(path),
            next_module_id=progress.next_module_id,
            created_at=path.created_at,
            updated_at=path.updated_at,
        )

    def to_detail(
        self,
        path: LearningPath,
        progress_rows: list[LearningPathModuleProgress],
    ) -> LearningPathDetail:
        """Build a full learning path response with module read state."""
        progress_by_module_id = {progress.module_id: progress for progress in progress_rows}
        return LearningPathDetail(
            id=path.id,
            topic=path.topic,
            title=path.title,
            summary=path.summary,
            estimated_minutes=self.estimated_minutes(path),
            progress=self.to_progress(path, progress_rows),
            modules=[
                self.to_module_read(module, progress_by_module_id.get(module.id))
                for module in path.modules
            ],
            created_at=path.created_at,
            updated_at=path.updated_at,
        )

    def to_module_read(
        self,
        module: LearningPathModule,
        progress: LearningPathModuleProgress | None,
    ) -> LearningPathModuleRead:
        """Build a module response with read state."""
        return LearningPathModuleRead(
            id=module.id,
            order=module.order,
            title=module.title,
            learning_objective=module.learning_objective,
            estimated_minutes=module.estimated_minutes,
            blocks=self.to_lesson_blocks(module),
            is_read=progress.is_read if progress else False,
            read_at=progress.read_at if progress else None,
        )

    def to_lesson_blocks(self, module: LearningPathModule) -> list[LessonBlock]:
        """Rebuild typed lesson blocks from stored block rows."""
        return [
            lesson_block_adapter.validate_python(
                {
                    "id": block.id,
                    "order": block.order,
                    "type": block.block_type,
                    **block.content,
                }
            )
            for block in module.blocks
        ]

    def to_feedback_attempt(
        self,
        attempt: LearningPathFeedbackAttemptModel,
    ) -> LearningPathFeedbackAttempt:
        """Build the public feedback-attempt response."""
        return LearningPathFeedbackAttempt(
            id=attempt.id,
            learning_path_id=attempt.learning_path_id,
            module_id=attempt.module_id,
            lesson_block_id=attempt.lesson_block_id,
            question=attempt.question,
            answer=attempt.answer,
            ai_response=LearningPathFeedbackResponse(
                feedback=attempt.feedback,
                strengths=attempt.strengths,
                improvements=attempt.improvements,
                suggested_answer=attempt.suggested_answer,
            ),
            created_at=attempt.created_at,
        )

    def to_content_response(self, path: LearningPath) -> ContentResponse:
        """Build the generated-content response from a persisted learning path."""
        return ContentResponse(
            id=path.id,
            topic=path.topic,
            title=path.title,
            summary=path.summary,
            modules=[
                ContentModule(
                    id=module.id,
                    order=module.order,
                    title=module.title,
                    learning_objective=module.learning_objective,
                    estimated_minutes=module.estimated_minutes,
                    blocks=self.to_lesson_blocks(module),
                )
                for module in path.modules
            ],
        )

    def estimated_minutes(self, path: LearningPath) -> int:
        """Return total estimated minutes across path modules."""
        return sum(module.estimated_minutes for module in path.modules)


learning_path = CRUDLearningPath()
