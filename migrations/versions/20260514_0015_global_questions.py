"""Add global_questions table.

Revision ID: 20260514_0015
Revises: 20260508_0014
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260514_0015"
down_revision = "20260508_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "global_questions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("question_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index(
        "ix_global_questions_question_hash",
        "global_questions",
        ["question_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_global_questions_question_hash", table_name="global_questions")
    op.drop_table("global_questions")
