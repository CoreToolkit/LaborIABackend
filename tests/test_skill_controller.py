import os
import uuid
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

import api.profiles as profiles_module
from core.database import Base
from core.jwt import create_token
from models.profile import Profile
from models.user import User


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
app = FastAPI()
app.include_router(profiles_module.router, prefix="/api")
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

    app.dependency_overrides[profiles_module.get_db] = override_db
    yield
    app.dependency_overrides.clear()


def _create_user(email: str | None = None) -> User:
    db = TestSessionLocal()
    try:
        unique_email = email or f"skill-controller-{uuid.uuid4().hex}@example.com"
        user = User(
            email=unique_email,
            name="Skill Controller User",
            profile_picture=None,
            oauth_provider="google",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _create_profile(user_id: int) -> Profile:
    db = TestSessionLocal()
    try:
        profile = Profile(user_id=user_id, full_name="Skill Controller Profile")
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
    finally:
        db.close()


def _auth_headers_for_user(user: User) -> dict:
    token = create_token(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.profile_picture,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_my_skills():
    user = _create_user()
    _create_profile(user.id)
    headers = _auth_headers_for_user(user)

    created = client.post(
        "/api/profiles/me/skills",
        json={"name": "Python", "category": "backend", "level": "advanced"},
        headers=headers,
    )
    assert created.status_code == 201
    created_data = created.json()
    assert created_data["name"] == "Python"
    assert created_data["category"] == "backend"

    listed = client.get("/api/profiles/me/skills", headers=headers)
    assert listed.status_code == 200
    listed_data = listed.json()
    assert len(listed_data) == 1
    assert listed_data[0]["id"] == created_data["id"]


def test_list_my_skills_requires_existing_profile():
    user = _create_user()
    headers = _auth_headers_for_user(user)

    response = client.get("/api/profiles/me/skills", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


def test_update_and_delete_my_skill_flow():
    user = _create_user()
    _create_profile(user.id)
    headers = _auth_headers_for_user(user)

    created = client.post(
        "/api/profiles/me/skills",
        json={"name": "Python", "level": "mid"},
        headers=headers,
    )
    assert created.status_code == 201
    skill_id = created.json()["id"]

    updated = client.put(
        f"/api/profiles/me/skills/{skill_id}",
        json={"level": "senior", "category": "backend"},
        headers=headers,
    )
    assert updated.status_code == 200
    updated_data = updated.json()
    assert updated_data["level"] == "senior"
    assert updated_data["category"] == "backend"

    deleted = client.delete(f"/api/profiles/me/skills/{skill_id}", headers=headers)
    assert deleted.status_code == 204

    listed = client.get("/api/profiles/me/skills", headers=headers)
    assert listed.status_code == 200
    assert listed.json() == []


def test_update_skill_not_owned_returns_404():
    owner = _create_user()
    stranger = _create_user()
    _create_profile(owner.id)
    _create_profile(stranger.id)
    owner_headers = _auth_headers_for_user(owner)
    stranger_headers = _auth_headers_for_user(stranger)

    created = client.post(
        "/api/profiles/me/skills",
        json={"name": "Python"},
        headers=owner_headers,
    )
    assert created.status_code == 201
    skill_id = created.json()["id"]

    updated = client.put(
        f"/api/profiles/me/skills/{skill_id}",
        json={"level": "expert"},
        headers=stranger_headers,
    )

    assert updated.status_code == 404
    assert updated.json()["detail"] == "Skill not found"
