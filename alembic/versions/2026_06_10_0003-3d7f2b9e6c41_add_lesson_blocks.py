"""add lesson blocks.

Replace the fixed module body columns with typed lesson blocks. Existing
module content is converted into markdown and reflection_review blocks.
The downgrade restores the old columns from the blocks best-effort: markdown
blocks merge into ``explanation`` and the first reflection_review block
becomes ``practice_prompt``/``success_criteria``; other detail is lost.

Revision ID: 3d7f2b9e6c41
Revises: 5b3ea99c4a01
Create Date: 2026-06-10 00:03:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3d7f2b9e6c41"
down_revision: str | None = "5b3ea99c4a01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _lesson_blocks_table() -> sa.Table:
    return sa.table(
        "learning_path_lesson_blocks",
        sa.column("module_id", sa.Integer),
        sa.column("order", sa.Integer),
        sa.column("block_type", sa.String),
        sa.column("content", postgresql.JSONB),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def _module_to_blocks(module: sa.RowMapping) -> list[dict[str, Any]]:
    """Convert one legacy module row into ordered lesson block payloads."""
    now = datetime.now(UTC)
    blocks: list[dict[str, Any]] = []

    def add(block_type: str, content: dict[str, Any]) -> None:
        blocks.append(
            {
                "module_id": module["id"],
                "order": len(blocks) + 1,
                "block_type": block_type,
                "content": content,
                "created_at": now,
                "updated_at": now,
            }
        )

    if module["explanation"]:
        add("markdown", {"markdown": module["explanation"]})
    if module["key_points"]:
        bullets = "\n".join(f"- {point}" for point in module["key_points"])
        add("markdown", {"markdown": f"**Key points**\n\n{bullets}"})
    if module["example"]:
        add("markdown", {"markdown": f"**Example**\n\n{module['example']}"})
    if module["practice_prompt"]:
        add(
            "reflection_review",
            {
                "prompt": module["practice_prompt"],
                "review_criteria": module["success_criteria"]
                or ["Review your answer against the module objective."],
            },
        )
    if not blocks:
        add("markdown", {"markdown": module["title"]})
    return blocks


def upgrade() -> None:
    op.create_table(
        "learning_path_lesson_blocks",
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.String(length=50), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["module_id"], ["learning_path_modules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "module_id",
            "order",
            name="uq_learning_path_lesson_blocks_module_order",
        ),
    )
    op.create_index(
        op.f("ix_learning_path_lesson_blocks_id"),
        "learning_path_lesson_blocks",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_path_lesson_blocks_module_id"),
        "learning_path_lesson_blocks",
        ["module_id"],
        unique=False,
    )

    conn = op.get_bind()
    modules = conn.execute(
        sa.text(
            "SELECT id, title, explanation, key_points, example, "
            "practice_prompt, success_criteria FROM learning_path_modules"
        )
    ).mappings()
    rows = [block for module in modules for block in _module_to_blocks(module)]
    if rows:
        op.bulk_insert(_lesson_blocks_table(), rows)

    op.drop_column("learning_path_modules", "explanation")
    op.drop_column("learning_path_modules", "key_points")
    op.drop_column("learning_path_modules", "example")
    op.drop_column("learning_path_modules", "practice_prompt")
    op.drop_column("learning_path_modules", "success_criteria")


def downgrade() -> None:
    op.add_column(
        "learning_path_modules",
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "learning_path_modules",
        sa.Column(
            "key_points",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "learning_path_modules",
        sa.Column("example", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "learning_path_modules",
        sa.Column("practice_prompt", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "learning_path_modules",
        sa.Column(
            "success_criteria",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE learning_path_modules AS modules
            SET explanation = merged.markdown
            FROM (
                SELECT module_id,
                       string_agg(content->>'markdown', E'\n\n' ORDER BY "order") AS markdown
                FROM learning_path_lesson_blocks
                WHERE block_type = 'markdown'
                GROUP BY module_id
            ) AS merged
            WHERE merged.module_id = modules.id
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE learning_path_modules AS modules
            SET practice_prompt = reflection.prompt,
                success_criteria = reflection.review_criteria
            FROM (
                SELECT DISTINCT ON (module_id)
                       module_id,
                       content->>'prompt' AS prompt,
                       content->'review_criteria' AS review_criteria
                FROM learning_path_lesson_blocks
                WHERE block_type = 'reflection_review'
                ORDER BY module_id, "order"
            ) AS reflection
            WHERE reflection.module_id = modules.id
            """
        )
    )
    for column in ("explanation", "key_points", "example", "practice_prompt", "success_criteria"):
        op.alter_column("learning_path_modules", column, server_default=None)

    op.drop_index(
        op.f("ix_learning_path_lesson_blocks_module_id"),
        table_name="learning_path_lesson_blocks",
    )
    op.drop_index(
        op.f("ix_learning_path_lesson_blocks_id"),
        table_name="learning_path_lesson_blocks",
    )
    op.drop_table("learning_path_lesson_blocks")
