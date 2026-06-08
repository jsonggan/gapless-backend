"""add learning paths.

Revision ID: 8f3a1c6d9b24
Revises: 19c4da7a49eb
Create Date: 2026-06-08 00:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8f3a1c6d9b24"
down_revision: str | None = "19c4da7a49eb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_paths",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_paths_id"), "learning_paths", ["id"], unique=False)
    op.create_index(op.f("ix_learning_paths_user_id"), "learning_paths", ["user_id"], unique=False)
    op.create_table(
        "learning_path_modules",
        sa.Column("learning_path_id", sa.Integer(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("learning_objective", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("key_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("example", sa.Text(), nullable=False),
        sa.Column("practice_prompt", sa.Text(), nullable=False),
        sa.Column("success_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["learning_path_id"], ["learning_paths.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_path_id",
            "order",
            name="uq_learning_path_modules_path_order",
        ),
    )
    op.create_index(
        op.f("ix_learning_path_modules_id"),
        "learning_path_modules",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_path_modules_learning_path_id"),
        "learning_path_modules",
        ["learning_path_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_learning_path_modules_learning_path_id"),
        table_name="learning_path_modules",
    )
    op.drop_index(op.f("ix_learning_path_modules_id"), table_name="learning_path_modules")
    op.drop_table("learning_path_modules")
    op.drop_index(op.f("ix_learning_paths_user_id"), table_name="learning_paths")
    op.drop_index(op.f("ix_learning_paths_id"), table_name="learning_paths")
    op.drop_table("learning_paths")
