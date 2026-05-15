"""Add user_metrics, recommendations, badges, user_badges tables.

Revision ID: 20260501_0008
Revises: 20260415_0007
Create Date: 2026-05-01
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import CHAR, TypeDecorator


# revision identifiers, used by Alembic.
revision = "20260501_0008"
down_revision = "d0ef6ed3cbe0"
branch_labels = None
depends_on = None


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


def upgrade() -> None:
    # 1. badges (no FK dependencies on new tables)
    op.create_table(
        "badges",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("condition_type", sa.String(), nullable=True),
        sa.Column("condition_value", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    )

    # 2. user_metrics (FK → users)
    op.create_table(
        "user_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("total_interviews", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_by_skill", sa.JSON(), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_user_metrics_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", name="uq_user_metrics_user_id"),
    )
    op.create_index("ix_user_metrics_user_id", "user_metrics", ["user_id"], unique=True)

    # 3. recommendations (FK → users, job_roles)
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", GUID(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_recommendations_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["job_roles.id"],
            name="fk_recommendations_role_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"], unique=False)
    op.create_index("ix_recommendations_role_id", "recommendations", ["role_id"], unique=False)

    # 4. user_badges (FK → users, badges)
    op.create_table(
        "user_badges",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("badge_id", sa.Integer(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_user_badges_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["badge_id"], ["badges.id"],
            name="fk_user_badges_badge_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "badge_id", name="uq_user_badges_user_badge"),
    )
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"], unique=False)
    op.create_index("ix_user_badges_badge_id", "user_badges", ["badge_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_badges_badge_id", table_name="user_badges")
    op.drop_index("ix_user_badges_user_id", table_name="user_badges")
    op.drop_table("user_badges")

    op.drop_index("ix_recommendations_role_id", table_name="recommendations")
    op.drop_index("ix_recommendations_user_id", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_user_metrics_user_id", table_name="user_metrics")
    op.drop_table("user_metrics")

    op.drop_table("badges")
