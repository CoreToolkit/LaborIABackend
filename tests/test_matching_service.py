import uuid
from decimal import Decimal
from datetime import date
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


def _create_experience(
    db,
    profile_id: int,
    *,
    start_date: date,
    end_date: date | None = None,
    currently_working: bool = False,
):
    from models.experience import Experience

    experience = Experience(
        profile_id=profile_id,
        position="Backend Developer",
        company="LaborIA",
        start_date=start_date,
        end_date=end_date,
        currently_working=currently_working,
    )
    db.add(experience)
    db.commit()
    db.refresh(experience)
    return experience


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


def test_detect_skill_gaps_returns_empty_list_when_role_has_no_role_skills():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "Python")
        role = _create_role(db)
        service = MatchingService(db)

        assert service.detect_skill_gaps(user.id, role.id) == []
    finally:
        db.close()


def test_detect_skill_gaps_returns_all_role_skills_when_user_has_no_profile():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        role = _create_role(db)
        fastapi = _create_technology(db, "FastAPI")
        docker = _create_technology(db, "Docker")
        _create_role_skill(db, role.id, fastapi.id, 9)
        _create_role_skill(db, role.id, docker.id, 4)
        service = MatchingService(db)

        assert service.detect_skill_gaps(user.id, role.id) == [
            {"name": "FastAPI", "importance_weight": 9, "is_required": False},
            {"name": "Docker", "importance_weight": 4, "is_required": False},
        ]
    finally:
        db.close()


def test_detect_skill_gaps_returns_all_role_skills_when_user_has_no_skills():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        _create_profile(db, user.id)
        role = _create_role(db)
        fastapi = _create_technology(db, "FastAPI")
        docker = _create_technology(db, "Docker")
        _create_role_skill(db, role.id, fastapi.id, 9)
        _create_role_skill(db, role.id, docker.id, 4)
        service = MatchingService(db)

        assert service.detect_skill_gaps(user.id, role.id) == [
            {"name": "FastAPI", "importance_weight": 9, "is_required": False},
            {"name": "Docker", "importance_weight": 4, "is_required": False},
        ]
    finally:
        db.close()


def test_detect_skill_gaps_returns_only_missing_skills_for_partial_match():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "Python")

        role = _create_role(db)
        python = _create_technology(db, "Python")
        docker = _create_technology(db, "Docker")
        fastapi = _create_technology(db, "FastAPI")
        _create_role_skill(db, role.id, python.id, 10)
        _create_role_skill(db, role.id, docker.id, 8)
        _create_role_skill(db, role.id, fastapi.id, 6)
        service = MatchingService(db)

        assert service.detect_skill_gaps(user.id, role.id) == [
            {"name": "Docker", "importance_weight": 8, "is_required": False},
            {"name": "FastAPI", "importance_weight": 6, "is_required": False},
        ]
    finally:
        db.close()


def test_detect_skill_gaps_orders_by_importance_weight_desc():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        _create_profile(db, user.id)

        role = _create_role(db)
        docker = _create_technology(db, "Docker")
        python = _create_technology(db, "Python")
        fastapi = _create_technology(db, "FastAPI")
        _create_role_skill(db, role.id, docker.id, 3)
        _create_role_skill(db, role.id, python.id, 9)
        _create_role_skill(db, role.id, fastapi.id, 6)
        service = MatchingService(db)

        gaps = service.detect_skill_gaps(user.id, role.id)

        assert [gap["name"] for gap in gaps] == ["Python", "FastAPI", "Docker"]
    finally:
        db.close()


def test_detect_skill_gaps_is_case_insensitive():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "python")

        role = _create_role(db)
        python = _create_technology(db, "Python")
        docker = _create_technology(db, "Docker")
        _create_role_skill(db, role.id, python.id, 9)
        _create_role_skill(db, role.id, docker.id, 4)
        service = MatchingService(db)

        assert service.detect_skill_gaps(user.id, role.id) == [
            {"name": "Docker", "importance_weight": 4, "is_required": False},
        ]
    finally:
        db.close()


def test_detect_skill_gaps_applies_trim_and_space_normalization():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "  Machine   Learning ")

        role = _create_role(db)
        machine_learning = _create_technology(db, "Machine Learning")
        docker = _create_technology(db, "Docker")
        _create_role_skill(db, role.id, machine_learning.id, 10)
        _create_role_skill(db, role.id, docker.id, 4)
        service = MatchingService(db)

        assert service.detect_skill_gaps(user.id, role.id) == [
            {"name": "Docker", "importance_weight": 4, "is_required": False},
        ]
    finally:
        db.close()


def test_detect_skill_gaps_ignores_duplicate_user_skills():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        _create_skill(db, profile.id, "Python")
        _create_skill(db, profile.id, " python ")

        role = _create_role(db)
        python = _create_technology(db, "Python")
        fastapi = _create_technology(db, "FastAPI")
        _create_role_skill(db, role.id, python.id, 8)
        _create_role_skill(db, role.id, fastapi.id, 5)
        service = MatchingService(db)

        assert service.detect_skill_gaps(user.id, role.id) == [
            {"name": "FastAPI", "importance_weight": 5, "is_required": False},
        ]
    finally:
        db.close()


def test_detect_skill_gaps_deduplicates_role_requirements_by_normalized_name():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        _create_profile(db, user.id)

        role = _create_role(db)
        react = _create_technology(db, "React")
        react_trimmed = _create_technology(db, " react ")
        docker = _create_technology(db, "Docker")
        _create_role_skill(db, role.id, react.id, 7)
        _create_role_skill(db, role.id, react_trimmed.id, 9)
        _create_role_skill(db, role.id, docker.id, 4)
        service = MatchingService(db)

        assert service.detect_skill_gaps(user.id, role.id) == [
            {"name": "react", "importance_weight": 9, "is_required": False},
            {"name": "Docker", "importance_weight": 4, "is_required": False},
        ]
    finally:
        db.close()


def test_calculate_experience_match_returns_zero_when_user_has_no_profile():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        role = _create_role(db)
        service = MatchingService(db)

        assert service.calculate_experience_match(user.id, role.id) == 0.0
    finally:
        db.close()


def test_calculate_experience_match_returns_zero_when_user_has_no_experiences():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        _create_profile(db, user.id)
        role = _create_role(db)
        service = MatchingService(db)

        assert service.calculate_experience_match(user.id, role.id) == 0.0
    finally:
        db.close()


def test_calculate_experience_match_returns_one_hundred_when_user_meets_exact_minimum():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        role = _create_role(db)
        role.seniority_level = SeniorityLevel.MID
        db.commit()

        _create_experience(
            db,
            profile.id,
            start_date=date(2022, 1, 1),
            end_date=date(2024, 1, 1),
        )

        service = MatchingService(db)

        assert service.calculate_experience_match(user.id, role.id) == 100.0
    finally:
        db.close()


def test_calculate_experience_match_returns_one_hundred_when_user_exceeds_minimum():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        role = _create_role(db)
        role.seniority_level = SeniorityLevel.MID
        db.commit()

        _create_experience(
            db,
            profile.id,
            start_date=date(2020, 1, 1),
            end_date=date(2024, 1, 1),
        )

        service = MatchingService(db)

        assert service.calculate_experience_match(user.id, role.id) == 100.0
    finally:
        db.close()


def test_calculate_experience_match_returns_proportional_score_when_user_does_not_meet_minimum():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        role = _create_role(db)
        role.seniority_level = SeniorityLevel.SENIOR
        db.commit()

        _create_experience(
            db,
            profile.id,
            start_date=date(2022, 1, 1),
            end_date=date(2024, 1, 1),
        )

        service = MatchingService(db)

        assert service.calculate_experience_match(user.id, role.id) == 50.0
    finally:
        db.close()


def test_calculate_experience_match_is_clamped_between_zero_and_one_hundred():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        role = _create_role(db)
        role.seniority_level = SeniorityLevel.JUNIOR
        db.commit()

        _create_experience(
            db,
            profile.id,
            start_date=date(2015, 1, 1),
            end_date=date(2025, 1, 1),
        )

        service = MatchingService(db)
        result = service.calculate_experience_match(user.id, role.id)

        assert 0.0 <= result <= 100.0
        assert result == 100.0
    finally:
        db.close()


def test_calculate_experience_match_treats_missing_end_date_without_current_flag_conservatively():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        role = _create_role(db)
        role.seniority_level = SeniorityLevel.JUNIOR
        db.commit()

        _create_experience(
            db,
            profile.id,
            start_date=date(2024, 1, 1),
            end_date=None,
            currently_working=False,
        )

        service = MatchingService(db)

        assert service.calculate_experience_match(user.id, role.id) == 0.0
    finally:
        db.close()


def test_calculate_experience_match_handles_zero_length_experience_as_zero():
    db = TestSessionLocal()
    try:
        user = _create_user(db)
        profile = _create_profile(db, user.id)
        role = _create_role(db)
        role.seniority_level = SeniorityLevel.JUNIOR
        db.commit()

        _create_experience(
            db,
            profile.id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
        )

        service = MatchingService(db)

        assert service.calculate_experience_match(user.id, role.id) == 0.0
    finally:
        db.close()
