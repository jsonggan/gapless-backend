"""Learning path SQLAlchemy models."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
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
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    example: Mapped[str] = mapped_column(Text, nullable=False)
    practice_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    success_criteria: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    learning_path: Mapped[LearningPath] = relationship(back_populates="modules")
