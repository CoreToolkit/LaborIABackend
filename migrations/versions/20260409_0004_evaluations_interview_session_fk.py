"""Make evaluations.interview_session_id a real FK to interview_sessions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260409_0004"
down_revision = "26c8185480b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.alter_column(
            "interview_session_id",
            existing_type=sa.String(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_evaluations_interview_session_id",
            "interview_sessions",
            ["interview_session_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.drop_constraint("fk_evaluations_interview_session_id", type_="foreignkey")
        batch_op.alter_column(
            "interview_session_id",
            existing_type=sa.Integer(),
            type_=sa.String(),
            existing_nullable=False,
        )
