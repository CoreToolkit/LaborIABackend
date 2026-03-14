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

import api.roles as roles_module
from core.database import Base
from core.jwt import create_token
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel


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

    assert response.status_code == 403
