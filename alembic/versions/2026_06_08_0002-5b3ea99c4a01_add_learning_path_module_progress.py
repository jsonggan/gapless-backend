"""add learning path module progress.

Revision ID: 5b3ea99c4a01
Revises: 8f3a1c6d9b24
Create Date: 2026-06-08 00:02:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b3ea99c4a01"
down_revision: str | None = "8f3a1c6d9b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_path_module_progress",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["module_id"], ["learning_path_modules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "module_id",
            name="uq_learning_path_module_progress_user_module",
        ),
    )
    op.create_index(
        op.f("ix_learning_path_module_progress_id"),
        "learning_path_module_progress",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_path_module_progress_module_id"),
        "learning_path_module_progress",
        ["module_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_path_module_progress_user_id"),
        "learning_path_module_progress",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_learning_path_module_progress_user_id"),
        table_name="learning_path_module_progress",
    )
    op.drop_index(
        op.f("ix_learning_path_module_progress_module_id"),
        table_name="learning_path_module_progress",
    )
    op.drop_index(
        op.f("ix_learning_path_module_progress_id"),
        table_name="learning_path_module_progress",
    )
    op.drop_table("learning_path_module_progress")
