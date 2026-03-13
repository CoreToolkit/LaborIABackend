import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression, func
from sqlalchemy.types import CHAR, TypeDecorator

from core.database import Base


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True))
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


class JobRoleCategory(enum.Enum):
    TECH = "tech"
    DATA = "data"
    DESIGN = "design"


class SeniorityLevel(enum.Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"


class RoleEnglishLevel(enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class JobRole(Base):
    __tablename__ = "job_roles"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(
        Enum(
            JobRoleCategory,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="job_role_category_enum",
        ),
        nullable=False,
    )
    seniority_level = Column(
        Enum(
            SeniorityLevel,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="job_role_seniority_level_enum",
        ),
        nullable=False,
    )
    min_english_level = Column(
        Enum(
            RoleEnglishLevel,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="job_role_english_level_enum",
        ),
        nullable=False,
    )
    estimated_salary_min_cop = Column(Numeric(12, 2), nullable=True)
    estimated_salary_max_cop = Column(Numeric(12, 2), nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default=expression.true())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    role_skills = relationship("RoleSkill", back_populates="job_role", cascade="all, delete-orphan")
