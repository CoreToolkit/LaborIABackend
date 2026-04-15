import os
import uuid
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["JWT_SECRET"] = "test-secret"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.user import User
from services.group_interview_session_service import GroupInterviewSessionService


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


def _create_user(db, email: str | None = None) -> User:
    unique_email = email or f"group-session-service-{uuid.uuid4().hex}@example.com"
    user = User(
        email=unique_email,
        name="Group Session Service User",
        profile_picture=None,
        oauth_provider="google",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_role(db) -> JobRole:
    role = JobRole(
        id=uuid.uuid4(),
        name="Senior Python Developer",
        description="Senior Python Developer description",
        category=JobRoleCategory.TECH,
        seniority_level=SeniorityLevel.MID,
        min_english_level=RoleEnglishLevel.B2,
        estimated_salary_min_cop=3000000,
        estimated_salary_max_cop=6000000,
        active=True,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def test_join_group_session_creates_interview_session_once():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        role = _create_role(db)
        service = GroupInterviewSessionService(db)

        group_session = service.create_group_session(
            host_id=user.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        returned_group_session, interview_session = service.join_group_session(
            session_code=group_session.session_code,
            user_id=user.id,
        )

        assert returned_group_session.id == group_session.id
        assert interview_session.user_id == user.id
        assert interview_session.group_interview_session_id == group_session.id

        _, interview_session_again = service.join_group_session(
            session_code=group_session.session_code,
            user_id=user.id,
        )

        assert interview_session_again.id == interview_session.id
    finally:
        db.close()


def test_join_group_session_invalid_code_raises_not_found():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        service = GroupInterviewSessionService(db)

        with pytest.raises(InterviewSessionNotFoundError):
            service.join_group_session(session_code="ZZZZ0000", user_id=user.id)
    finally:
        db.close()


def test_create_group_session_defaults_to_waiting_status():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        role = _create_role(db)
        service = GroupInterviewSessionService(db)

        group_session = service.create_group_session(
            host_id=user.id,
            role_id=str(role.id),
            difficulty="beginner",
        )

        assert group_session.status == "waiting"
    finally:
        db.close()


def test_start_group_session_as_host_changes_status_to_in_progress():
    db = TestSessionLocal()
    try:
        host = _create_user(db)
        role = _create_role(db)
        service = GroupInterviewSessionService(db)

        group_session = service.create_group_session(
            host_id=host.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        started = service.start_group_session(group_session.session_code, host.id)
        assert started.status == "in_progress"
    finally:
        db.close()


def test_start_group_session_not_host_raises_permission_error():
    db = TestSessionLocal()
    try:
        host = _create_user(db, email=f"host-{uuid.uuid4().hex}@example.com")
        other_user = _create_user(db, email=f"other-{uuid.uuid4().hex}@example.com")
        role = _create_role(db)
        service = GroupInterviewSessionService(db)

        group_session = service.create_group_session(
            host_id=host.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        with pytest.raises(PermissionError):
            service.start_group_session(group_session.session_code, other_user.id)
    finally:
        db.close()


def test_start_group_session_when_already_started_raises_value_error():
    db = TestSessionLocal()
    try:
        host = _create_user(db)
        role = _create_role(db)
        service = GroupInterviewSessionService(db)

        group_session = service.create_group_session(
            host_id=host.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        service.start_group_session(group_session.session_code, host.id)

        with pytest.raises(ValueError):
            service.start_group_session(group_session.session_code, host.id)
    finally:
        db.close()


def test_close_group_session_as_host_changes_status_to_closed():
    db = TestSessionLocal()
    try:
        host = _create_user(db)
        role = _create_role(db)
        service = GroupInterviewSessionService(db)

        group_session = service.create_group_session(
            host_id=host.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        service.start_group_session(group_session.session_code, host.id)
        closed = service.close_group_session(group_session.session_code, host.id)
        assert closed.status == "closed"
    finally:
        db.close()


def test_close_group_session_not_host_raises_permission_error():
    db = TestSessionLocal()
    try:
        host = _create_user(db, email=f"host-{uuid.uuid4().hex}@example.com")
        other_user = _create_user(db, email=f"other-{uuid.uuid4().hex}@example.com")
        role = _create_role(db)
        service = GroupInterviewSessionService(db)

        group_session = service.create_group_session(
            host_id=host.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        service.start_group_session(group_session.session_code, host.id)

        with pytest.raises(PermissionError):
            service.close_group_session(group_session.session_code, other_user.id)
    finally:
        db.close()


def test_close_group_session_when_waiting_raises_value_error():
    db = TestSessionLocal()
    try:
        host = _create_user(db)
        role = _create_role(db)
        service = GroupInterviewSessionService(db)

        group_session = service.create_group_session(
            host_id=host.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        with pytest.raises(ValueError):
            service.close_group_session(group_session.session_code, host.id)
    finally:
        db.close()
