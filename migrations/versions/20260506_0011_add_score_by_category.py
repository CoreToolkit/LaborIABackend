"""Add score_by_category to user_metrics.

Revision ID: 20260506_0011
Revises: 20260501_0010
Create Date: 2026-05-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260506_0011"
down_revision = "20260501_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_metrics",
        sa.Column("score_by_category", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_metrics", "score_by_category")
