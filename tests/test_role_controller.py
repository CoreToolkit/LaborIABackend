import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from core.config import settings as app_settings

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import api.roles as roles_module
from core.database import Base
from core.jwt import create_token
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.role_skill import RoleSkill
from models.technology import Technology


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
app = FastAPI()
app.include_router(roles_module.router, prefix="/api")
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[roles_module.get_db] = override_db
    yield
    app.dependency_overrides.clear()


def _auth_headers() -> dict:
    token = create_token(
        {
            "id": 999,
            "email": "roles@example.com",
            "name": "Roles User",
            "picture": None,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _auth_headers_for_email(email: str) -> dict:
    token = create_token(
        {
            "id": 999,
            "email": email,
            "name": "Roles User",
            "picture": None,
        }
    )
    return {"Authorization": f"Bearer {token}"}


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


def test_list_roles_returns_paginated_payload():
    _create_role(name="Backend Developer")
    _create_role(name="Data Analyst", category=JobRoleCategory.DATA)
    headers = _auth_headers()

    response = client.get("/api/roles?page=1&size=1", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["size"] == 1
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Backend Developer"


def test_list_roles_applies_filters():
    _create_role(name="Backend Developer", category=JobRoleCategory.TECH, active=True)
    _create_role(name="Data Analyst", category=JobRoleCategory.DATA, active=True)
    _create_role(name="Inactive Backend", category=JobRoleCategory.TECH, active=False)
    headers = _auth_headers()

    response = client.get("/api/roles?name=backend&category=tech&active=true", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Backend Developer"


def test_list_roles_requires_authentication():
    response = client.get("/api/roles")

    assert response.status_code == 401


def test_get_role_detail_returns_complete_payload():
    role = _create_role(name="Backend Developer", seniority_level=SeniorityLevel.SENIOR, min_english_level=RoleEnglishLevel.B2)
    technology = _create_technology("FastAPI")
    _create_role_skill(role.id, technology.id, importance_weight=9, is_required=True)
    headers = _auth_headers()

    response = client.get(f"/api/roles/{role.id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(role.id)
    assert data["name"] == "Backend Developer"
    assert data["seniority_level"] == "senior"
    assert len(data["role_skills"]) == 1
    assert data["role_skills"][0]["technology_name"] == "FastAPI"
    assert data["role_skills"][0]["importance_weight"] == 9
    assert data["role_skills"][0]["is_required"] is True


def test_get_role_detail_returns_404_when_role_does_not_exist():
    headers = _auth_headers()

    response = client.get(f"/api/roles/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Role not found"


def test_create_role_returns_201_for_admin(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")
    technology = _create_technology("FastAPI")
    headers = _auth_headers_for_email("admin@example.com")

    response = client.post(
        "/api/roles",
        json={
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
        },
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Backend Developer"
    assert len(data["role_skills"]) == 1
    assert data["role_skills"][0]["technology_name"] == "FastAPI"


def test_create_role_returns_403_for_non_admin(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")
    headers = _auth_headers_for_email("user@example.com")

    response = client.post(
        "/api/roles",
        json={
            "name": "Backend Developer",
            "category": "tech",
            "seniority_level": "mid",
            "min_english_level": "B2",
        },
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges are required"


def test_create_role_returns_422_for_invalid_schema(monkeypatch):
    monkeypatch.setattr(app_settings, "ADMIN_EMAILS", "admin@example.com")
    headers = _auth_headers_for_email("admin@example.com")

    response = client.post(
        "/api/roles",
        json={
            "name": "Backend Developer",
            "category": "tech",
            "seniority_level": "mid",
            "min_english_level": "B2",
            "estimated_salary_min_cop": "6000000",
            "estimated_salary_max_cop": "5000000",
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_create_role_requires_authentication():
    response = client.post(
        "/api/roles",
        json={
            "name": "Backend Developer",
            "category": "tech",
            "seniority_level": "mid",
            "min_english_level": "B2",
        },
    )

    assert response.status_code == 401
