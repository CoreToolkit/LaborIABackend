"""Add improvement_plans, improvement_plan_items, improvement_plan_history tables.

Revision ID: 20260507_0013
Revises: 20260507_0012
Create Date: 2026-05-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260507_0013"
down_revision = "20260507_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "improvement_plans",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_evaluation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "improvement_plan_items",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("improvement_plans.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("skill", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False, server_default="medium"),
        sa.Column("current_score", sa.Float(), nullable=True),
        sa.Column("target_score", sa.Float(), nullable=False, server_default="70.0"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("resources", sa.JSON(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "improvement_plan_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("improvement_plan_history")
    op.drop_table("improvement_plan_items")
    op.drop_table("improvement_plans")
