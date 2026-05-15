import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from core.config import settings as app_settings

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from exceptions.role_exceptions import RoleAuthorizationError, RoleNotFoundError, RoleValidationError
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.role_skill import RoleSkill
from models.technology import Technology
from schemas.role import RoleCreateSchema
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


def _create_technology(name: str) -> Technology:
    db = TestSessionLocal()
    try:
        technology = Technology(name=name)
        db.add(technology)
        db.commit()
        db.refresh(technology)
        return technology
    finally:
        db.close()


def _create_role_skill(role_id, technology_id: int, importance_weight: int = 8, is_required: bool = True) -> RoleSkill:
    db = TestSessionLocal()
    try:
        role_skill = RoleSkill(
            role_id=role_id,
            technology_id=technology_id,
            importance_weight=importance_weight,
            is_required=is_required,
        )
        db.add(role_skill)
        db.commit()
        db.refresh(role_skill)
        return role_skill
    finally:
        db.close()


def _admin_user() -> dict:
    return {"email": "admin@example.com"}


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


def test_get_role_detail_returns_role_with_requirements():
    role = _create_role(name="Backend Developer")
    technology = _create_technology("FastAPI")
    _create_role_skill(role.id, technology.id, importance_weight=9, is_required=True)

    db = TestSessionLocal()
    try:
        service = RoleService(db)
        result = service.get_role_detail(role.id)

        assert result.id == role.id
        assert result.name == "Backend Developer"
        assert len(result.role_skills) == 1
        assert result.role_skills[0].technology.name == "FastAPI"
    finally:
        db.close()


def test_get_role_detail_raises_not_found_for_unknown_id():
    db = TestSessionLocal()
    try:
        service = RoleService(db)

        with pytest.raises(RoleNotFoundError):
            service.get_role_detail(uuid.uuid4())
    finally:
        db.close()


def test_create_role_creates_role_with_requirements_for_admin(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")
    technology = _create_technology("FastAPI")

    db = TestSessionLocal()
    try:
        service = RoleService(db)
        result = service.create_role(
            RoleCreateSchema.model_validate(
                {
                    "name": "Backend Developer",
                    "description": "Builds APIs",
                    "category": "tech",
                    "seniority_level": "mid",
                    "min_english_level": "B2",
                    "role_skills": [
                        {
                            "technology_id": technology.id,
                            "importance_weight": 9,
                            "is_required": True,
                        }
                    ],
                }
            ),
            _admin_user(),
        )

        assert result.name == "Backend Developer"
        assert len(result.role_skills) == 1
        assert result.role_skills[0].technology.name == "FastAPI"
    finally:
        db.close()


def test_create_role_raises_for_non_admin(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")

    db = TestSessionLocal()
    try:
        service = RoleService(db)

        with pytest.raises(RoleAuthorizationError):
            service.create_role(
                RoleCreateSchema.model_validate(
                    {
                        "name": "Backend Developer",
                        "category": "tech",
                        "seniority_level": "mid",
                        "min_english_level": "B2",
                    }
                ),
                {"email": "user@example.com"},
            )
    finally:
        db.close()


def test_create_role_raises_when_technology_does_not_exist(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")

    db = TestSessionLocal()
    try:
        service = RoleService(db)

        with pytest.raises(RoleValidationError):
            service.create_role(
                RoleCreateSchema.model_validate(
                    {
                        "name": "Backend Developer",
                        "category": "tech",
                        "seniority_level": "mid",
                        "min_english_level": "B2",
                        "role_skills": [
                            {
                                "technology_id": 999,
                                "importance_weight": 9,
                                "is_required": True,
                            }
                        ],
                    }
                ),
                _admin_user(),
            )
    finally:
        db.close()
