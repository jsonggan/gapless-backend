"""add learning path feedback attempts.

Revision ID: 9c2d4e7f1a8b
Revises: 3d7f2b9e6c41
Create Date: 2026-06-13 00:04:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9c2d4e7f1a8b"
down_revision: str | None = "3d7f2b9e6c41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_path_feedback_attempts",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("learning_path_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("lesson_block_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column(
            "strengths",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "improvements",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("suggested_answer", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["learning_path_id"],
            ["learning_paths.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_block_id"],
            ["learning_path_lesson_blocks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["learning_path_modules.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_learning_path_feedback_attempts_id"),
        "learning_path_feedback_attempts",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_path_feedback_attempts_learning_path_id"),
        "learning_path_feedback_attempts",
        ["learning_path_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_path_feedback_attempts_lesson_block_id"),
        "learning_path_feedback_attempts",
        ["lesson_block_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_path_feedback_attempts_module_id"),
        "learning_path_feedback_attempts",
        ["module_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_path_feedback_attempts_user_id"),
        "learning_path_feedback_attempts",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_learning_path_feedback_attempts_user_id"),
        table_name="learning_path_feedback_attempts",
    )
    op.drop_index(
        op.f("ix_learning_path_feedback_attempts_module_id"),
        table_name="learning_path_feedback_attempts",
    )
    op.drop_index(
        op.f("ix_learning_path_feedback_attempts_lesson_block_id"),
        table_name="learning_path_feedback_attempts",
    )
    op.drop_index(
        op.f("ix_learning_path_feedback_attempts_learning_path_id"),
        table_name="learning_path_feedback_attempts",
    )
    op.drop_index(
        op.f("ix_learning_path_feedback_attempts_id"),
        table_name="learning_path_feedback_attempts",
    )
    op.drop_table("learning_path_feedback_attempts")
