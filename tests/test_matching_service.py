import uuid
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from exceptions.role_exceptions import RoleNotFoundError
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.profile import Profile
from models.role_skill import RoleSkill
from models.skill import Skill
from models.technology import Technology
from models.user import User
from services.matching_service import MatchingService


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


def _create_user(db, email: str = "matching@example.com") -> User:
    user = User(
        email=email,
        name="Matching User",
        profile_picture=None,
        oauth_provider="google",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_profile(db, user_id: int) -> Profile:
    profile = Profile(user_id=user_id, full_name="Matching Profile")
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _create_skill(db, profile_id: int, name: str) -> Skill:
    skill = Skill(profile_id=profile_id, name=name)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def _create_role(
    db,
    *,
    name: str = "Backend Developer",
    role_id=None,
) -> JobRole:
    role = JobRole(
        id=role_id or uuid.uuid4(),
        name=name,
        description=f"{name} description",
        category=JobRoleCategory.TECH,
        seniority_level=SeniorityLevel.MID,
        min_english_level=RoleEnglishLevel.B2,
        estimated_salary_min_cop=Decimal("3000000"),
        estimated_salary_max_cop=Decimal("5000000"),
        active=True,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def _create_technology(db, name: str) -> Technology:
    technology = Technology(name=name)
    db.add(technology)
    db.commit()
    db.refresh(technology)
    return technology


def _create_role_skill(db, role_id, technology_id: int, importance_weight: int) -> RoleSkill:
    role_skill = RoleSkill(
        role_id=role_id,
        technology_id=technology_id,
        importance_weight=importance_weight,
        is_required=False,
    )
    db.add(role_skill)
    db.commit()
    db.refresh(role_skill)
    return role_skill


def test_calculate_skill_match_returns_zero_when_user_has_no_profile():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        role = _create_role(db)
        service = MatchingService(db)

        assert service.calculate_skill_match(user.id, role.id) == 0.0
    finally:
        db.close()


def test_calculate_skill_match_returns_zero_when_user_has_no_skills():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        _create_profile(db, user.id)
        role = _create_role(db)
        service = MatchingService(db)

        assert service.calculate_skill_match(user.id, role.id) == 0.0
    finally:
        db.close()


def test_calculate_skill_match_returns_zero_when_role_has_no_role_skills():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "Python")
        role = _create_role(db)
        service = MatchingService(db)

        assert service.calculate_skill_match(user.id, role.id) == 0.0
    finally:
        db.close()


def test_calculate_skill_match_returns_one_hundred_for_total_match():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "Python")
        _create_skill(db, profile.id, "FastAPI")

        role = _create_role(db)
        python = _create_technology(db, "Python")
        fastapi = _create_technology(db, "FastAPI")
        _create_role_skill(db, role.id, python.id, 7)
        _create_role_skill(db, role.id, fastapi.id, 3)

        service = MatchingService(db)

        assert service.calculate_skill_match(user.id, role.id) == 100.0
    finally:
        db.close()


def test_calculate_skill_match_returns_weighted_partial_match():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "Python")

        role = _create_role(db)
        python = _create_technology(db, "Python")
        fastapi = _create_technology(db, "FastAPI")
        docker = _create_technology(db, "Docker")
        _create_role_skill(db, role.id, python.id, 5)
        _create_role_skill(db, role.id, fastapi.id, 3)
        _create_role_skill(db, role.id, docker.id, 2)

        service = MatchingService(db)

        assert service.calculate_skill_match(user.id, role.id) == 50.0
    finally:
        db.close()


def test_calculate_skill_match_returns_zero_for_no_match():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "Django")

        role = _create_role(db)
        python = _create_technology(db, "Python")
        _create_role_skill(db, role.id, python.id, 10)

        service = MatchingService(db)

        assert service.calculate_skill_match(user.id, role.id) == 0.0
    finally:
        db.close()


def test_calculate_skill_match_is_case_insensitive():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "python")

        role = _create_role(db)
        python = _create_technology(db, "Python")
        _create_role_skill(db, role.id, python.id, 10)

        service = MatchingService(db)

        assert service.calculate_skill_match(user.id, role.id) == 100.0
    finally:
        db.close()


def test_calculate_skill_match_trims_and_collapses_spaces():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "  Machine   Learning  ")

        role = _create_role(db)
        machine_learning = _create_technology(db, "machine learning")
        _create_role_skill(db, role.id, machine_learning.id, 10)

        service = MatchingService(db)

        assert service.calculate_skill_match(user.id, role.id) == 100.0
    finally:
        db.close()


def test_calculate_skill_match_deduplicates_user_skills():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "Python")
        _create_skill(db, profile.id, " python ")

        role = _create_role(db)
        python = _create_technology(db, "Python")
        fastapi = _create_technology(db, "FastAPI")
        _create_role_skill(db, role.id, python.id, 4)
        _create_role_skill(db, role.id, fastapi.id, 6)

        service = MatchingService(db)

        assert service.calculate_skill_match(user.id, role.id) == 40.0
    finally:
        db.close()


def test_calculate_skill_match_raises_when_role_does_not_exist():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "Python")
        service = MatchingService(db)

        with pytest.raises(RoleNotFoundError):
            service.calculate_skill_match(user.id, uuid.uuid4())
    finally:
        db.close()
