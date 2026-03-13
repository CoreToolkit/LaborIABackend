import uuid

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from core.database import Base, SessionLocal, engine
from core.jwt import create_token
from main import app
from models.user import User


Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _create_user(email: str | None = None) -> User:
    db = SessionLocal()
    try:
        unique_email = email or f"profile-controller-{uuid.uuid4().hex}@example.com"
        user = User(
            email=unique_email,
            name="Profile Controller User",
            profile_picture=None,
            oauth_provider="google",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
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

def test_create_profile_success():
    user = _create_user()
    headers = _auth_headers_for_user(user)

    payload = {
        "full_name": "Controller Test User",
        "career": "Systems Engineer",
        "university": "ECI",
        "graduation_date": "2027-03-15",
        "description": "Fullstack developer",
        "english_level": "Intermediate",
        "preferred_location": "Bogota",
        "preferred_employment_type": "Internship",
        "salary_expectation": "2300000",
    }

    response = client.post("/profiles", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == user.id
    assert data["english_level"] == "Intermediate"
    assert data["preferred_employment_type"] == "Internship"


def test_create_profile_duplicate_returns_400():
    user = _create_user()
    headers = _auth_headers_for_user(user)

    first = client.post("/profiles", json={"full_name": "First"}, headers=headers)
    assert first.status_code == 201

    second = client.post("/profiles", json={"full_name": "Second"}, headers=headers)
    assert second.status_code == 400
    assert second.json()["detail"] == "User already has a profile"


def test_get_my_profile_not_found_returns_404():
    user = _create_user()
    headers = _auth_headers_for_user(user)

    response = client.get("/profiles/me", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


def test_update_and_delete_profile_flow():
    user = _create_user()
    headers = _auth_headers_for_user(user)

    created = client.post("/profiles", json={"full_name": "To Update"}, headers=headers)
    assert created.status_code == 201

    updated = client.put(
        "/profiles/me",
        json={
            "career": "Updated Career",
            "english_level": "Advanced",
            "referred_employment_type": "Internship",
        },
        headers=headers,
    )
    assert updated.status_code == 200
    updated_data = updated.json()
    assert updated_data["career"] == "Updated Career"
    assert updated_data["english_level"] == "Advanced"
    assert updated_data["preferred_employment_type"] == "Internship"

    deleted = client.delete("/profiles/me", headers=headers)
    assert deleted.status_code == 204

    after_delete = client.get("/profiles/me", headers=headers)
    assert after_delete.status_code == 404
