"""Add match results table."""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import CHAR, TypeDecorator


# revision identifiers, used by Alembic.
revision = "20260320_0002"
down_revision = "20260313_0001"
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
    op.create_table(
        "match_results",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", GUID(), nullable=False),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_match_results_user_id"),
        sa.ForeignKeyConstraint(["role_id"], ["job_roles.id"], name="fk_match_results_role_id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_match_results_user_role"),
        sa.CheckConstraint(
            "total_score >= 0 AND total_score <= 100",
            name="ck_match_results_total_score_range",
        ),
    )
    op.create_index("ix_match_results_user_id", "match_results", ["user_id"], unique=False)
    op.create_index("ix_match_results_role_id", "match_results", ["role_id"], unique=False)
    op.create_index("ix_match_results_total_score", "match_results", ["total_score"], unique=False)
    op.create_index(
        "ix_match_results_user_id_total_score",
        "match_results",
        ["user_id", "total_score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_match_results_user_id_total_score", table_name="match_results")
    op.drop_index("ix_match_results_total_score", table_name="match_results")
    op.drop_index("ix_match_results_role_id", table_name="match_results")
    op.drop_index("ix_match_results_user_id", table_name="match_results")
    op.drop_table("match_results")
