"""Add status to group interview sessions.

Revision ID: 20260415_0006
Revises: 20260410_0005
Create Date: 2026-04-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260415_0006"
down_revision = "20260410_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "group_interview_sessions",
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'waiting'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("group_interview_sessions", "status")