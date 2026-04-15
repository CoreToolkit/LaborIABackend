"""Add group interview rounds.

Revision ID: 20260415_0007
Revises: 20260415_0006
Create Date: 2026-04-15
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import CHAR, TypeDecorator


# revision identifiers, used by Alembic.
revision = "20260415_0007"
down_revision = "20260415_0006"
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
        "group_interview_rounds",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("group_interview_session_id", sa.Integer(), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=True),
        sa.Column("target_skill", sa.String(), nullable=True),
        sa.Column("difficulty", sa.String(), nullable=True),
        sa.Column("status", sa.Enum("ACTIVE", "CLOSED", "SKIPPED", name="groupinterviewroundstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["group_interview_session_id"], ["group_interview_sessions.id"], name="fk_group_interview_rounds_group_interview_session_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_group_interview_rounds_created_by"),
        sa.UniqueConstraint("group_interview_session_id", "round_index", name="uq_group_interview_rounds_session_round_index"),
    )
    op.create_index("ix_group_interview_rounds_group_interview_session_id", "group_interview_rounds", ["group_interview_session_id"], unique=False)
    op.create_index("ix_group_interview_rounds_created_by", "group_interview_rounds", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_group_interview_rounds_created_by", table_name="group_interview_rounds")
    op.drop_index("ix_group_interview_rounds_group_interview_session_id", table_name="group_interview_rounds")
    op.drop_table("group_interview_rounds")
    sa.Enum(name="groupinterviewroundstatus").drop(op.get_bind(), checkfirst=True)