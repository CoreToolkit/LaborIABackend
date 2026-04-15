"""add_evaluations_table

Revision ID: 26c8185480b3
Revises: 20260320_0002
Create Date: 2026-03-27 19:34:48.730256

"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import CHAR, TypeDecorator



# revision identifiers, used by Alembic.
revision = '26c8185480b3'
down_revision = '20260320_0002'
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
        "evaluations",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("interview_session_id", sa.String(), nullable=False),
        sa.Column("user_answer_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "COMPLETED", "FAILED", name="evaluationstatus"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("topics_covered", sa.JSON(), nullable=True),
        sa.Column("topics_missing", sa.JSON(), nullable=True),
        sa.Column("eval_version", sa.String(), nullable=False, server_default="1.0"),
        sa.Column("model_used", sa.String(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name="fk_evaluations_question_id"),
    )
    op.create_index("ix_evaluations_interview_session_id", "evaluations", ["interview_session_id"], unique=False)
    op.create_index("ix_evaluations_question_id", "evaluations", ["question_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evaluations_question_id", table_name="evaluations")
    op.drop_index("ix_evaluations_interview_session_id", table_name="evaluations")
    op.drop_table("evaluations")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS evaluationstatus")
