import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from core.config import settings as app_settings

pytest.importorskip("sqlalchemy")

os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["JWT_SECRET"] = "test-secret"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from exceptions.technology_exceptions import (
    TechnologyAuthorizationError,
    TechnologyInUseError,
    TechnologyNotFoundError,
    TechnologyValidationError,
)
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.role_skill import RoleSkill
from models.technology import Technology
from schemas.technology import TechnologyCreate, TechnologyUpdate
from services.technology_service import TechnologyService


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


def _admin_user() -> dict:
    return {"email": "admin@example.com"}


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


def _create_role() -> JobRole:
    db = TestSessionLocal()
    try:
        role = JobRole(
            id=uuid.uuid4(),
            name="Backend Developer",
            description="Builds APIs",
            category=JobRoleCategory.TECH,
            seniority_level=SeniorityLevel.MID,
            min_english_level=RoleEnglishLevel.B2,
            estimated_salary_min_cop=Decimal("3000000"),
            estimated_salary_max_cop=Decimal("5000000"),
            active=True,
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        return role
    finally:
        db.close()


def _create_role_skill(role_id, technology_id: int) -> RoleSkill:
    db = TestSessionLocal()
    try:
        role_skill = RoleSkill(
            role_id=role_id,
            technology_id=technology_id,
            importance_weight=9,
            is_required=True,
        )
        db.add(role_skill)
        db.commit()
        db.refresh(role_skill)
        return role_skill
    finally:
        db.close()


def test_list_technologies_returns_paginated_items():
    _create_technology("FastAPI")
    _create_technology("React")

    db = TestSessionLocal()
    try:
        service = TechnologyService(db)
        result = service.list_technologies(page=1, size=1)

        assert result["page"] == 1
        assert result["size"] == 1
        assert result["total"] == 2
        assert len(result["items"]) == 1
    finally:
        db.close()


def test_create_update_and_detail_technology_flow(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")

    db = TestSessionLocal()
    try:
        service = TechnologyService(db)
        created = service.create_technology(TechnologyCreate(name="FastAPI"), _admin_user())
        detailed = service.get_technology_detail(created.id)

        assert created.name == "FastAPI"
        assert detailed.name == "FastAPI"

        updated = service.update_technology(created.id, TechnologyUpdate(name="FastAPI v2"), _admin_user())
        assert updated.name == "FastAPI v2"
    finally:
        db.close()


def test_get_technology_detail_raises_not_found_for_unknown_id():
    db = TestSessionLocal()
    try:
        service = TechnologyService(db)

        with pytest.raises(TechnologyNotFoundError):
            service.get_technology_detail(999)
    finally:
        db.close()


def test_create_technology_raises_for_non_admin(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")

    db = TestSessionLocal()
    try:
        service = TechnologyService(db)

        with pytest.raises(TechnologyAuthorizationError):
            service.create_technology(TechnologyCreate(name="FastAPI"), {"email": "user@example.com"})
    finally:
        db.close()


def test_create_technology_raises_for_duplicate_name(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")
    _create_technology("FastAPI")

    db = TestSessionLocal()
    try:
        service = TechnologyService(db)

        with pytest.raises(TechnologyValidationError):
            service.create_technology(TechnologyCreate(name="fastapi"), _admin_user())
    finally:
        db.close()


def test_delete_technology_raises_when_in_use(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")
    technology = _create_technology("FastAPI")
    role = _create_role()
    _create_role_skill(role.id, technology.id)

    db = TestSessionLocal()
    try:
        service = TechnologyService(db)

        with pytest.raises(TechnologyInUseError):
            service.delete_technology(technology.id, _admin_user())
    finally:
        db.close()


def test_delete_technology_raises_not_found_for_unknown_id(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")

    db = TestSessionLocal()
    try:
        service = TechnologyService(db)

        with pytest.raises(TechnologyNotFoundError):
            service.delete_technology(999, _admin_user())
    finally:
        db.close()
