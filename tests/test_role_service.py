import uuid
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from services.role_service import RoleService


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


def _create_role(
    *,
    name: str,
    category: JobRoleCategory = JobRoleCategory.TECH,
    seniority_level: SeniorityLevel = SeniorityLevel.JUNIOR,
    min_english_level: RoleEnglishLevel = RoleEnglishLevel.B1,
    active: bool = True,
) -> JobRole:
    db = TestSessionLocal()
    try:
        role = JobRole(
            id=uuid.uuid4(),
            name=name,
            description=f"{name} description",
            category=category,
            seniority_level=seniority_level,
            min_english_level=min_english_level,
            estimated_salary_min_cop=Decimal("3000000"),
            estimated_salary_max_cop=Decimal("5000000"),
            active=active,
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        return role
    finally:
        db.close()


def test_list_roles_returns_paginated_items():
    _create_role(name="Backend Developer")
    _create_role(name="Data Analyst", category=JobRoleCategory.DATA)

    db = TestSessionLocal()
    try:
        service = RoleService(db)
        result = service.list_roles(page=1, size=1)

        assert result["page"] == 1
        assert result["size"] == 1
        assert result["total"] == 2
        assert len(result["items"]) == 1
        assert result["items"][0].name == "Backend Developer"
    finally:
        db.close()


def test_list_roles_applies_filters():
    _create_role(name="Backend Developer", category=JobRoleCategory.TECH, active=True)
    _create_role(name="Data Analyst", category=JobRoleCategory.DATA, active=True)
    _create_role(name="Inactive Backend", category=JobRoleCategory.TECH, active=False)

    db = TestSessionLocal()
    try:
        service = RoleService(db)
        result = service.list_roles(page=1, size=10, name="backend", category=JobRoleCategory.TECH, active=True)

        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0].name == "Backend Developer"
    finally:
        db.close()
