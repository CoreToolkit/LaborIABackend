import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import api.technologies as technologies_module
from core.database import Base
from core.jwt import create_token
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.role_skill import RoleSkill
from models.technology import Technology


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
app = FastAPI()
app.include_router(technologies_module.router, prefix="/api")
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

    app.dependency_overrides[technologies_module.get_db] = override_db
    yield
    app.dependency_overrides.clear()


def _auth_headers(email: str = "user@example.com") -> dict:
    token = create_token(
        {
            "id": 999,
            "email": email,
            "name": "Technology User",
            "picture": None,
        }
    )
    return {"Authorization": f"Bearer {token}"}


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


def test_list_technologies_returns_paginated_payload():
    _create_technology("FastAPI")
    _create_technology("React")
    headers = _auth_headers()

    response = client.get("/api/technologies?page=1&size=1", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["size"] == 1
    assert data["total"] == 2
    assert len(data["items"]) == 1


def test_get_technology_detail_returns_payload():
    technology = _create_technology("FastAPI")
    headers = _auth_headers()

    response = client.get(f"/api/technologies/{technology.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "FastAPI"


def test_get_technology_detail_returns_404_when_not_found():
    headers = _auth_headers()

    response = client.get("/api/technologies/999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Technology not found"


def test_create_technology_returns_201_for_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    headers = _auth_headers("admin@example.com")

    response = client.post("/api/technologies", json={"name": "FastAPI"}, headers=headers)

    assert response.status_code == 201
    assert response.json()["name"] == "FastAPI"


def test_update_technology_returns_200_for_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    technology = _create_technology("FastAPI")
    headers = _auth_headers("admin@example.com")

    response = client.put(f"/api/technologies/{technology.id}", json={"name": "FastAPI v2"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "FastAPI v2"


def test_update_technology_returns_404_when_not_found(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    headers = _auth_headers("admin@example.com")

    response = client.put("/api/technologies/999", json={"name": "FastAPI v2"}, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Technology not found"


def test_delete_technology_returns_204_for_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    technology = _create_technology("FastAPI")
    headers = _auth_headers("admin@example.com")

    response = client.delete(f"/api/technologies/{technology.id}", headers=headers)

    assert response.status_code == 204


def test_delete_technology_returns_409_when_in_use(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    technology = _create_technology("FastAPI")
    role = _create_role()
    _create_role_skill(role.id, technology.id)
    headers = _auth_headers("admin@example.com")

    response = client.delete(f"/api/technologies/{technology.id}", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Technology is in use by one or more roles"


def test_write_operations_require_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    headers = _auth_headers("user@example.com")

    response = client.post("/api/technologies", json={"name": "FastAPI"}, headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges are required"


def test_read_operations_require_authentication():
    response = client.get("/api/technologies")

    assert response.status_code == 401
