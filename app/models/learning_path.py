"""Learning path SQLAlchemy models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIDMixin, TimestampMixin


class LearningPath(Base, IntegerIDMixin, TimestampMixin):
    """Generated learning path owned by a user."""

    __tablename__ = "learning_paths"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    modules: Mapped[list[LearningPathModule]] = relationship(
        back_populates="learning_path",
        cascade="all, delete-orphan",
        order_by="LearningPathModule.order",
    )


class LearningPathModule(Base, IntegerIDMixin, TimestampMixin):
    """Ordered module inside a generated learning path."""

    __tablename__ = "learning_path_modules"
    __table_args__ = (
        UniqueConstraint(
            "learning_path_id",
            "order",
            name="uq_learning_path_modules_path_order",
        ),
    )

    learning_path_id: Mapped[int] = mapped_column(
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    learning_objective: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    learning_path: Mapped[LearningPath] = relationship(back_populates="modules")
    blocks: Mapped[list[LearningPathLessonBlock]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="LearningPathLessonBlock.order",
    )
    progress: Mapped[list[LearningPathModuleProgress]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
    )


class LearningPathLessonBlock(Base, IntegerIDMixin, TimestampMixin):
    """Ordered typed lesson block inside a learning path module.

    ``block_type`` discriminates the frontend block union (markdown, process,
    single_choice_question, reflection_review); ``content`` holds the
    type-specific payload.
    """

    __tablename__ = "learning_path_lesson_blocks"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "order",
            name="uq_learning_path_lesson_blocks_module_order",
        ),
    )

    module_id: Mapped[int] = mapped_column(
        ForeignKey("learning_path_modules.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    module: Mapped[LearningPathModule] = relationship(back_populates="blocks")


class LearningPathModuleProgress(Base, IntegerIDMixin, TimestampMixin):
    """Per-user read state for an individual learning path module."""

    __tablename__ = "learning_path_module_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "module_id",
            name="uq_learning_path_module_progress_user_module",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    module_id: Mapped[int] = mapped_column(
        ForeignKey("learning_path_modules.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    module: Mapped[LearningPathModule] = relationship(back_populates="progress")
