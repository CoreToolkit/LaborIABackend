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
from exceptions.profile_exceptions import ProfileNotFoundError, SkillNotFoundError
from models.profile import Profile
from models.user import User
from schemas.skill import SkillCreate, SkillUpdate
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
    unique_email = email or f"skill-service-{uuid.uuid4().hex}@example.com"
    user = User(
        email=unique_email,
        name="Skill Service User",
        profile_picture=None,
        oauth_provider="google",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_profile(db, user_id: int) -> Profile:
    profile = Profile(user_id=user_id, full_name="Skill Profile")
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def test_create_and_list_skills_for_current_profile():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        service = ProfileService(db)

        created = service.create_skill(
            user.id,
            SkillCreate(name="Python", category="backend", level="advanced"),
        )

        listed = service.list_skills(user.id)

        assert created.profile_id == profile.id
        assert len(listed) == 1
        assert listed[0].id == created.id
    finally:
        db.close()


def test_create_skill_raises_not_found_when_profile_does_not_exist():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        service = ProfileService(db)

        with pytest.raises(ProfileNotFoundError):
            service.create_skill(user.id, SkillCreate(name="Python"))
    finally:
        db.close()


def test_update_skill_raises_not_found_when_skill_is_not_owned():
    db = TestSessionLocal()
    try:
        owner = _create_user(db)
        stranger = _create_user(db)
        _create_profile(db, owner.id)
        _create_profile(db, stranger.id)
        service = ProfileService(db)
        created = service.create_skill(owner.id, SkillCreate(name="Python"))

        with pytest.raises(SkillNotFoundError):
            service.update_skill(stranger.id, created.id, SkillUpdate(level="expert"))
    finally:
        db.close()


def test_update_and_delete_skill_flow():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        _create_profile(db, user.id)
        service = ProfileService(db)
        created = service.create_skill(user.id, SkillCreate(name="Python", level="mid"))

        updated = service.update_skill(user.id, created.id, SkillUpdate(level="senior", category="backend"))
        assert updated.level == "senior"
        assert updated.category == "backend"

        service.delete_skill(user.id, created.id)
        assert service.list_skills(user.id) == []
    finally:
        db.close()
