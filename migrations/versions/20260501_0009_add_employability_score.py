"""Add employability_score to user_metrics.

Revision ID: 20260501_0009
Revises: 20260501_0008
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260501_0009"
down_revision = "20260501_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_metrics",
        sa.Column("employability_score", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_metrics", "employability_score")
