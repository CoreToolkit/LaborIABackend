"""Add job roles, technologies, and role skills tables."""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import CHAR, TypeDecorator


# revision identifiers, used by Alembic.
revision = "20260313_0001"
down_revision = None
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


JOB_ROLE_CATEGORY_VALUES = ("tech", "data", "design")
JOB_ROLE_SENIORITY_VALUES = ("junior", "mid", "senior")
JOB_ROLE_ENGLISH_VALUES = ("A1", "A2", "B1", "B2", "C1", "C2")


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_check_constraint(inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    )


def _has_foreign_key(inspector, table_name: str, constrained_columns: tuple[str, ...]) -> bool:
    expected = list(constrained_columns)
    return any(
        fk.get("constrained_columns") == expected
        for fk in inspector.get_foreign_keys(table_name)
    )


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _create_job_roles_table() -> None:
    op.create_table(
        "job_roles",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                *JOB_ROLE_CATEGORY_VALUES,
                name="job_role_category_enum",
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "seniority_level",
            sa.Enum(
                *JOB_ROLE_SENIORITY_VALUES,
                name="job_role_seniority_level_enum",
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "min_english_level",
            sa.Enum(
                *JOB_ROLE_ENGLISH_VALUES,
                name="job_role_english_level_enum",
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
            ),
            nullable=False,
        ),
        sa.Column("estimated_salary_min_cop", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_salary_max_cop", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
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
    )
    op.create_index("ix_job_roles_name", "job_roles", ["name"], unique=False)


def _ensure_job_roles_shape(inspector) -> None:
    columns = _column_names(inspector, "job_roles")
    if "id" not in columns:
        op.add_column("job_roles", sa.Column("id", GUID(), nullable=True))
    if "name" not in columns:
        op.add_column("job_roles", sa.Column("name", sa.String(), nullable=False))
    if "description" not in columns:
        op.add_column("job_roles", sa.Column("description", sa.Text(), nullable=True))
    if "category" not in columns:
        op.add_column(
            "job_roles",
            sa.Column(
                "category",
                sa.Enum(
                    *JOB_ROLE_CATEGORY_VALUES,
                    name="job_role_category_enum",
                    native_enum=False,
                    create_constraint=True,
                    validate_strings=True,
                ),
                nullable=False,
            ),
        )
    if "seniority_level" not in columns:
        op.add_column(
            "job_roles",
            sa.Column(
                "seniority_level",
                sa.Enum(
                    *JOB_ROLE_SENIORITY_VALUES,
                    name="job_role_seniority_level_enum",
                    native_enum=False,
                    create_constraint=True,
                    validate_strings=True,
                ),
                nullable=False,
            ),
        )
    if "min_english_level" not in columns:
        op.add_column(
            "job_roles",
            sa.Column(
                "min_english_level",
                sa.Enum(
                    *JOB_ROLE_ENGLISH_VALUES,
                    name="job_role_english_level_enum",
                    native_enum=False,
                    create_constraint=True,
                    validate_strings=True,
                ),
                nullable=False,
            ),
        )
    if "estimated_salary_min_cop" not in columns:
        op.add_column(
            "job_roles",
            sa.Column("estimated_salary_min_cop", sa.Numeric(12, 2), nullable=True),
        )
    if "estimated_salary_max_cop" not in columns:
        op.add_column(
            "job_roles",
            sa.Column("estimated_salary_max_cop", sa.Numeric(12, 2), nullable=True),
        )
    if "active" not in columns:
        op.add_column(
            "job_roles",
            sa.Column(
                "active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )

    if not _has_index(inspector, "job_roles", "ix_job_roles_name"):
        op.create_index("ix_job_roles_name", "job_roles", ["name"], unique=False)

    if not _has_check_constraint(inspector, "job_roles", "job_role_category_enum"):
        op.create_check_constraint(
            "job_role_category_enum",
            "job_roles",
            "category IN ('tech', 'data', 'design')",
        )
    if not _has_check_constraint(inspector, "job_roles", "job_role_seniority_level_enum"):
        op.create_check_constraint(
            "job_role_seniority_level_enum",
            "job_roles",
            "seniority_level IN ('junior', 'mid', 'senior')",
        )
    if not _has_check_constraint(inspector, "job_roles", "job_role_english_level_enum"):
        op.create_check_constraint(
            "job_role_english_level_enum",
            "job_roles",
            "min_english_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')",
        )


def _create_technologies_table() -> None:
    op.create_table(
        "technologies",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("name", name="uq_technologies_name"),
    )


def _ensure_technologies_shape(inspector) -> None:
    columns = _column_names(inspector, "technologies")
    if "id" not in columns:
        op.add_column("technologies", sa.Column("id", sa.Integer(), nullable=True))
    if "name" not in columns:
        op.add_column("technologies", sa.Column("name", sa.String(), nullable=False))
    if "created_at" not in columns:
        op.add_column(
            "technologies",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.func.now(),
            ),
        )


def _create_role_skills_table() -> None:
    op.create_table(
        "role_skills",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("role_id", GUID(), nullable=False),
        sa.Column("technology_id", sa.Integer(), nullable=False),
        sa.Column("importance_weight", sa.Integer(), nullable=False),
        sa.Column(
            "is_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.ForeignKeyConstraint(["role_id"], ["job_roles.id"], name="fk_role_skills_role_id"),
        sa.ForeignKeyConstraint(
            ["technology_id"],
            ["technologies.id"],
            name="fk_role_skills_technology_id",
        ),
        sa.CheckConstraint(
            "importance_weight >= 1 AND importance_weight <= 10",
            name="ck_role_skills_importance_weight_range",
        ),
    )
    op.create_index("ix_role_skills_role_id", "role_skills", ["role_id"], unique=False)
    op.create_index(
        "ix_role_skills_technology_id",
        "role_skills",
        ["technology_id"],
        unique=False,
    )


def _ensure_role_skills_shape(inspector) -> None:
    columns = _column_names(inspector, "role_skills")
    if "id" not in columns:
        op.add_column("role_skills", sa.Column("id", sa.Integer(), nullable=True))
    if "role_id" not in columns:
        op.add_column("role_skills", sa.Column("role_id", GUID(), nullable=False))
    if "technology_id" not in columns:
        op.add_column("role_skills", sa.Column("technology_id", sa.Integer(), nullable=False))
    if "importance_weight" not in columns:
        op.add_column(
            "role_skills",
            sa.Column("importance_weight", sa.Integer(), nullable=False),
        )
    if "is_required" not in columns:
        op.add_column(
            "role_skills",
            sa.Column(
                "is_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    if not _has_foreign_key(inspector, "role_skills", ("role_id",)):
        op.create_foreign_key(
            "fk_role_skills_role_id",
            "role_skills",
            "job_roles",
            ["role_id"],
            ["id"],
        )
    if not _has_foreign_key(inspector, "role_skills", ("technology_id",)):
        op.create_foreign_key(
            "fk_role_skills_technology_id",
            "role_skills",
            "technologies",
            ["technology_id"],
            ["id"],
        )

    if not _has_check_constraint(
        inspector,
        "role_skills",
        "ck_role_skills_importance_weight_range",
    ):
        op.create_check_constraint(
            "ck_role_skills_importance_weight_range",
            "role_skills",
            "importance_weight >= 1 AND importance_weight <= 10",
        )

    if not _has_index(inspector, "role_skills", "ix_role_skills_role_id"):
        op.create_index("ix_role_skills_role_id", "role_skills", ["role_id"], unique=False)
    if not _has_index(inspector, "role_skills", "ix_role_skills_technology_id"):
        op.create_index(
            "ix_role_skills_technology_id",
            "role_skills",
            ["technology_id"],
            unique=False,
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "job_roles" not in tables:
        _create_job_roles_table()
    else:
        _ensure_job_roles_shape(inspector)

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "technologies" not in tables:
        _create_technologies_table()
    else:
        _ensure_technologies_shape(inspector)

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "role_skills" not in tables:
        _create_role_skills_table()
    else:
        _ensure_role_skills_shape(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "role_skills" in tables:
        if _has_index(inspector, "role_skills", "ix_role_skills_role_id"):
            op.drop_index("ix_role_skills_role_id", table_name="role_skills")
        if _has_index(inspector, "role_skills", "ix_role_skills_technology_id"):
            op.drop_index("ix_role_skills_technology_id", table_name="role_skills")
        op.drop_table("role_skills")

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "job_roles" in tables:
        if _has_index(inspector, "job_roles", "ix_job_roles_name"):
            op.drop_index("ix_job_roles_name", table_name="job_roles")
        op.drop_table("job_roles")

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "technologies" in tables:
        op.drop_table("technologies")
