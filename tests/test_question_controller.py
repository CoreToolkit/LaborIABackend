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

import api.questions as questions_module
from core.database import Base
from core.jwt import create_token
from models.interview_session import InterviewSession
from models.question import Question
from models.user import User


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
app = FastAPI()
app.include_router(questions_module.router, prefix="/api")
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

    app.dependency_overrides[questions_module.get_db] = override_db
    yield
    app.dependency_overrides.clear()


def _create_user(email: str | None = None) -> User:
    db = TestSessionLocal()
    try:
        unique_email = email or f"question-controller-{uuid.uuid4().hex}@example.com"
        user = User(
            email=unique_email,
            name="Question Controller User",
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


def test_create_question_for_authenticated_user_session():
    user = _create_user()
    session = _create_interview_session(user.id)
    headers = _auth_headers_for_user(user)

    payload = {
        "question_text": "Tell me about a backend system you built.",
        "interview_session_id": session.id,
        "category": "backend",
        "difficulty": "medium",
        "expected_topics": ["architecture", "scalability"],
    }

    response = client.post("/api/questions", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["interview_session_id"] == session.id
    assert data["question_text"] == payload["question_text"]
    assert data["category"] == payload["category"]
    assert data["difficulty"] == payload["difficulty"]
    assert data["expected_topics"] == payload["expected_topics"]

    db = TestSessionLocal()
    try:
        saved_question = db.query(Question).filter(Question.id == data["id"]).first()
        assert saved_question is not None
        assert saved_question.interview_session_id == session.id
        assert saved_question.question_text == payload["question_text"]
    finally:
        db.close()


def test_create_question_returns_404_for_foreign_session():
    owner = _create_user()
    stranger = _create_user()
    session = _create_interview_session(owner.id)
    headers = _auth_headers_for_user(stranger)

    payload = {
        "question_text": "How do you handle failures?",
        "interview_session_id": session.id,
    }

    response = client.post("/api/questions", json=payload, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Interview session not found"


def test_create_question_requires_authentication():
    response = client.post(
        "/api/questions",
        json={
            "question_text": "What is dependency injection?",
            "interview_session_id": 1,
        },
    )

    assert response.status_code == 401
