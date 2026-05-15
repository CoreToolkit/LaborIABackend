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
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileValidationError,
)
from models.profile import EmploymentType, EnglishLevel
from models.user import User
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
    unique_email = email or f"profile-service-{uuid.uuid4().hex}@example.com"
    user = User(
        email=unique_email,
        name="Profile Service User",
        profile_picture=None,
        oauth_provider="google",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_profile_success_and_enum_conversion():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        service = ProfileService(db)

        profile = service.create_profile(
            user.id,
            {
                "full_name": "David Sarria",
                "career": "Systems Engineer",
                "english_level": "Intermediate",
                "referred_employment_type": "Internship",
                "salary_expectation": "2300000",
                "graduation_date": date(2027, 3, 15),
            },
        )

        assert profile.user_id == user.id
        assert profile.english_level == EnglishLevel.INTERMEDIATE
        assert profile.preferred_employment_type == EmploymentType.INTERNSHIP
    finally:
        db.close()


def test_create_profile_raises_when_user_already_has_profile():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        service = ProfileService(db)

        service.create_profile(user.id, {"full_name": "First Profile"})

        with pytest.raises(ProfileAlreadyExistsError):
            service.create_profile(user.id, {"full_name": "Second Profile"})
    finally:
        db.close()


def test_create_profile_raises_validation_error_for_invalid_english_level():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        service = ProfileService(db)

        with pytest.raises(ProfileValidationError):
            service.create_profile(user.id, {"english_level": "Fluent"})
    finally:
        db.close()


def test_update_profile_raises_not_found_when_profile_does_not_exist():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        service = ProfileService(db)

        with pytest.raises(ProfileNotFoundError):
            service.update_profile(user.id, {"career": "Updated Career"})
    finally:
        db.close()


def test_update_profile_success_with_enum_conversion():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        service = ProfileService(db)
        service.create_profile(user.id, {"full_name": "Profile To Update"})

        updated = service.update_profile(
            user.id,
            {
                "english_level": "Advanced",
                "preferred_employment_type": "Full-time",
            },
        )

        assert updated.english_level == EnglishLevel.ADVANCED
        assert updated.preferred_employment_type == EmploymentType.FULL_TIME
    finally:
        db.close()
