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

import api.sessions as sessions_module
from core.database import Base
from core.jwt import create_token
from models.interview_session import InterviewSession
from models.user import User


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
app = FastAPI()
app.include_router(sessions_module.router, prefix="/api")
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

    app.dependency_overrides[sessions_module.get_db] = override_db
    yield
    app.dependency_overrides.clear()


def _create_user(email: str | None = None) -> User:
    db = TestSessionLocal()
    try:
        unique_email = email or f"session-controller-{uuid.uuid4().hex}@example.com"
        user = User(
            email=unique_email,
            name="Session Controller User",
            profile_picture=None,
            oauth_provider="google",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _create_interview_session(user_id: int) -> InterviewSession:
    db = TestSessionLocal()
    try:
        session = InterviewSession(user_id=user_id)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
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


def test_get_session_detail_returns_session_for_authenticated_owner():
    user = _create_user()
    session = _create_interview_session(user.id)
    headers = _auth_headers_for_user(user)

    response = client.get(f"/api/sessions/{session.id}", headers=headers)

    assert response.status_code == 200
    assert set(response.json().keys()) == {"id", "user_id", "created_at", "updated_at"}
    assert response.json()["id"] == session.id
    assert response.json()["user_id"] == user.id


def test_get_session_detail_returns_404_when_not_found():
    user = _create_user()
    headers = _auth_headers_for_user(user)

    response = client.get("/api/sessions/999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Interview session not found"


def test_get_session_detail_returns_404_for_session_owned_by_another_user():
    owner = _create_user()
    stranger = _create_user()
    session = _create_interview_session(owner.id)
    headers = _auth_headers_for_user(stranger)

    response = client.get(f"/api/sessions/{session.id}", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Interview session not found"


def test_get_session_detail_requires_authentication():
    user = _create_user()
    session = _create_interview_session(user.id)

    response = client.get(f"/api/sessions/{session.id}")

    assert response.status_code == 401
