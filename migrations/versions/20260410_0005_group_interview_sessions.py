"""Add group interview sessions and link to interview sessions."""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import CHAR, TypeDecorator


# revision identifiers, used by Alembic.
revision = "20260410_0005"
down_revision = "20260409_0004"
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
        "group_interview_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("session_code", sa.String(), nullable=False),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("role_id", GUID(), nullable=False),
        sa.Column("difficulty", sa.String(), nullable=True),
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
        sa.ForeignKeyConstraint(["host_id"], ["users.id"], name="fk_group_interview_sessions_host_id"),
        sa.ForeignKeyConstraint(["role_id"], ["job_roles.id"], name="fk_group_interview_sessions_role_id"),
        sa.UniqueConstraint("session_code", name="uq_group_interview_sessions_session_code"),
    )
    op.create_index("ix_group_interview_sessions_session_code", "group_interview_sessions", ["session_code"], unique=True)
    op.create_index("ix_group_interview_sessions_host_id", "group_interview_sessions", ["host_id"], unique=False)
    op.create_index("ix_group_interview_sessions_role_id", "group_interview_sessions", ["role_id"], unique=False)

    with op.batch_alter_table("interview_sessions") as batch_op:
        batch_op.add_column(sa.Column("group_interview_session_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_interview_sessions_group_interview_session_id", ["group_interview_session_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_interview_sessions_group_interview_session_id",
            "group_interview_sessions",
            ["group_interview_session_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("interview_sessions") as batch_op:
        batch_op.drop_constraint("fk_interview_sessions_group_interview_session_id", type_="foreignkey")
        batch_op.drop_index("ix_interview_sessions_group_interview_session_id")
        batch_op.drop_column("group_interview_session_id")

    op.drop_index("ix_group_interview_sessions_role_id", table_name="group_interview_sessions")
    op.drop_index("ix_group_interview_sessions_host_id", table_name="group_interview_sessions")
    op.drop_index("ix_group_interview_sessions_session_code", table_name="group_interview_sessions")
    op.drop_table("group_interview_sessions")
