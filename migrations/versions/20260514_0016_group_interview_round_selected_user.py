"""Add selected_user_id to group_interview_rounds.

Revision ID: 20260514_0016
Revises: 20260514_0015
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260514_0016"
down_revision = "20260514_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "group_interview_rounds",
        sa.Column("selected_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(
        "ix_group_interview_rounds_selected_user_id",
        "group_interview_rounds",
        ["selected_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_group_interview_rounds_selected_user_id", table_name="group_interview_rounds")
    op.drop_column("group_interview_rounds", "selected_user_id")
