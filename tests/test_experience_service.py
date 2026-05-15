import os
import uuid
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["JWT_SECRET"] = "test-secret"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from exceptions.profile_exceptions import (
    ExperienceNotFoundError,
    ExperienceValidationError,
    ProfileNotFoundError,
)
from models.profile import Profile
from models.user import User
from schemas.experience import ExperienceCreate, ExperienceUpdate
from services.profile_service import ProfileService


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


def _create_user(db, email: str | None = None) -> User:
    unique_email = email or f"experience-service-{uuid.uuid4().hex}@example.com"
    user = User(
        email=unique_email,
        name="Experience Service User",
        profile_picture=None,
        oauth_provider="google",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_profile(db, user_id: int) -> Profile:
    profile = Profile(user_id=user_id, full_name="Experience Profile")
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def test_create_and_list_experiences_for_current_profile():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        service = ProfileService(db)

        created = service.create_experience(
            user.id,
            ExperienceCreate(
                position="Backend Developer",
                company="LaborIA",
                start_date=date(2024, 1, 10),
                end_date=date(2025, 1, 10),
                description="API work",
                currently_working=False,
            ),
        )

        listed = service.list_experiences(user.id)

        assert created.profile_id == profile.id
        assert len(listed) == 1
        assert listed[0].id == created.id
    finally:
        db.close()


def test_create_experience_raises_not_found_when_profile_does_not_exist():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        service = ProfileService(db)

        with pytest.raises(ProfileNotFoundError):
            service.create_experience(
                user.id,
                ExperienceCreate(
                    position="Backend Developer",
                    company="LaborIA",
                    start_date=date(2024, 1, 10),
                    currently_working=True,
                ),
            )
    finally:
        db.close()


def test_update_experience_clears_end_date_when_currently_working_becomes_true():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        _create_profile(db, user.id)
        service = ProfileService(db)
        created = service.create_experience(
            user.id,
            ExperienceCreate(
                position="Backend Developer",
                company="LaborIA",
                start_date=date(2024, 1, 10),
                end_date=date(2025, 1, 10),
            ),
        )

        updated = service.update_experience(
            user.id,
            created.id,
            ExperienceUpdate(currently_working=True),
        )

        assert updated.currently_working is True
        assert updated.end_date is None
    finally:
        db.close()


def test_update_experience_raises_not_found_when_experience_is_not_owned():
    db = TestSessionLocal()
    try:
        owner = _create_user(db)
        stranger = _create_user(db)
        _create_profile(db, owner.id)
        _create_profile(db, stranger.id)
        service = ProfileService(db)
        created = service.create_experience(
            owner.id,
            ExperienceCreate(
                position="Backend Developer",
                company="LaborIA",
                start_date=date(2024, 1, 10),
            ),
        )

        with pytest.raises(ExperienceNotFoundError):
            service.update_experience(
                stranger.id,
                created.id,
                ExperienceUpdate(company="Other Company"),
            )
    finally:
        db.close()


def test_update_experience_raises_validation_error_for_invalid_resolved_dates():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        _create_profile(db, user.id)
        service = ProfileService(db)
        created = service.create_experience(
            user.id,
            ExperienceCreate(
                position="Backend Developer",
                company="LaborIA",
                start_date=date(2024, 1, 10),
            ),
        )

        with pytest.raises(ExperienceValidationError):
            service.update_experience(
                user.id,
                created.id,
                ExperienceUpdate(end_date=date(2023, 12, 31)),
            )
    finally:
        db.close()
