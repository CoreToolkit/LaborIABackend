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
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.user import User
from services.group_interview_round_service import GroupInterviewRoundService
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
    unique_email = email or f"round-service-{uuid.uuid4().hex}@example.com"
    user = User(
        email=unique_email,
        name="Round Service User",
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


def test_create_next_round_starts_first_round_as_active():
    db = TestSessionLocal()
    try:
        host = _create_user(db)
        role = _create_role(db)
        group_session_service = GroupInterviewSessionService(db)
        round_service = GroupInterviewRoundService(db)

        group_session = group_session_service.create_group_session(
            host_id=host.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        round_item = round_service.create_next_round(
            group_session_id=group_session.id,
            question_text="What is Python?",
            target_skill="Python",
            difficulty="intermediate",
            created_by=host.id,
        )

        assert round_item.round_index == 1
        assert round_item.status.value == "active"
        assert round_service.get_active_round(group_session.id).id == round_item.id
    finally:
        db.close()


def test_create_next_round_closes_previous_active_round():
    db = TestSessionLocal()
    try:
        host = _create_user(db)
        role = _create_role(db)
        group_session_service = GroupInterviewSessionService(db)
        round_service = GroupInterviewRoundService(db)

        group_session = group_session_service.create_group_session(
            host_id=host.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        first_round = round_service.create_next_round(
            group_session_id=group_session.id,
            question_text="First question",
            created_by=host.id,
        )
        second_round = round_service.create_next_round(
            group_session_id=group_session.id,
            question_text="Second question",
            created_by=host.id,
        )

        assert first_round.status.value == "closed"
        assert second_round.round_index == 2
        assert second_round.status.value == "active"
        assert round_service.get_active_round(group_session.id).id == second_round.id
    finally:
        db.close()


def test_close_active_round_marks_it_closed():
    db = TestSessionLocal()
    try:
        host = _create_user(db)
        role = _create_role(db)
        group_session_service = GroupInterviewSessionService(db)
        round_service = GroupInterviewRoundService(db)

        group_session = group_session_service.create_group_session(
            host_id=host.id,
            role_id=str(role.id),
            difficulty="intermediate",
        )

        round_item = round_service.create_next_round(
            group_session_id=group_session.id,
            question_text="Question to close",
            created_by=host.id,
        )
        closed_round = round_service.close_active_round(group_session.id)

        assert closed_round.id == round_item.id
        assert closed_round.status.value == "closed"
        assert round_service.get_active_round(group_session.id) is None
    finally:
        db.close()