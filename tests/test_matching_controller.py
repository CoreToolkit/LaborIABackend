import os
import uuid
from datetime import date
from decimal import Decimal
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

import api.matching as matching_module
from core.database import Base
from core.jwt import create_token
from models.experience import Experience
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.match_result import MatchResult
from models.profile import Profile
from models.role_skill import RoleSkill
from models.skill import Skill
from models.technology import Technology
from models.user import User


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
app = FastAPI()
app.include_router(matching_module.router, prefix="/api")
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

    app.dependency_overrides[matching_module.get_db] = override_db
    yield
    app.dependency_overrides.clear()


def _create_user(email: str | None = None) -> User:
    db = TestSessionLocal()
    try:
        unique_email = email or f"matching-controller-{uuid.uuid4().hex}@example.com"
        user = User(
            email=unique_email,
            name="Matching Controller User",
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


def _create_profile(
    user_id: int,
    *,
    career: str | None = None,
    preferred_location: str | None = None,
    salary_expectation: Decimal | None = None,
) -> Profile:
    db = TestSessionLocal()
    try:
        profile = Profile(
            user_id=user_id,
            full_name="Matching Profile",
            career=career,
            preferred_location=preferred_location,
            salary_expectation=salary_expectation,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
    finally:
        db.close()


def _create_skill(profile_id: int, name: str) -> Skill:
    db = TestSessionLocal()
    try:
        skill = Skill(profile_id=profile_id, name=name)
        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill
    finally:
        db.close()


def _create_experience(
    profile_id: int,
    *,
    start_date,
    end_date=None,
    currently_working: bool = False,
) -> Experience:
    db = TestSessionLocal()
    try:
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
    finally:
        db.close()


def _create_role(
    *,
    name: str,
    active: bool = True,
    salary_min: Decimal | None = Decimal("3000000"),
    salary_max: Decimal | None = Decimal("5000000"),
    location: str | None = None,
) -> JobRole:
    db = TestSessionLocal()
    try:
        role = JobRole(
            id=uuid.uuid4(),
            name=name,
            description=f"{name} description",
            category=JobRoleCategory.TECH,
            seniority_level=SeniorityLevel.MID,
            min_english_level=RoleEnglishLevel.B2,
            estimated_salary_min_cop=salary_min,
            estimated_salary_max_cop=salary_max,
            active=active,
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        if location is not None:
            role.location = location
        return role
    finally:
        db.close()


def _create_technology(name: str) -> Technology:
    db = TestSessionLocal()
    try:
        technology = Technology(name=name)
        db.add(technology)
        db.commit()
        db.refresh(technology)
        return technology
    finally:
        db.close()


def _create_role_skill(role_id, technology_id: int, importance_weight: int = 10) -> RoleSkill:
    db = TestSessionLocal()
    try:
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
    finally:
        db.close()


def _count_match_results() -> int:
    db = TestSessionLocal()
    try:
        return db.query(MatchResult).count()
    finally:
        db.close()


def _list_match_results_for_user(user_id: int) -> list[MatchResult]:
    db = TestSessionLocal()
    try:
        return (
            db.query(MatchResult)
            .filter(MatchResult.user_id == user_id)
            .order_by(MatchResult.id.asc())
            .all()
        )
    finally:
        db.close()


def test_calculate_matching_returns_200_for_authenticated_user():
    user = _create_user()
    profile = _create_profile(
        user.id,
        career="Ingenieria de Sistemas",
        preferred_location="Bogota",
        salary_expectation=Decimal("4000000"),
    )
    _create_skill(profile.id, "Python")
    _create_experience(profile.id, start_date=date(2022, 1, 1), end_date=date(2024, 1, 1))
    role = _create_role(name="Backend Developer", location="Bogota")
    python = _create_technology("Python")
    _create_role_skill(role.id, python.id)

    response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    assert response.status_code == 200


def test_calculate_matching_requires_authentication():
    response = client.post("/api/matching/calculate")

    assert response.status_code == 401


def test_calculate_matching_processes_all_available_roles():
    user = _create_user()
    profile = _create_profile(user.id)
    _create_skill(profile.id, "Python")
    first_role = _create_role(name="Backend Developer")
    second_role = _create_role(name="Data Analyst")
    python = _create_technology("Python")
    _create_role_skill(first_role.id, python.id, 7)
    _create_role_skill(second_role.id, python.id, 9)

    response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    data = response.json()
    assert data["processed_roles"] == 2
    assert len(data["results"]) == 2
    assert {result["role_id"] for result in data["results"]} == {str(first_role.id), str(second_role.id)}


def test_calculate_matching_creates_initial_match_results():
    user = _create_user()
    profile = _create_profile(user.id)
    _create_skill(profile.id, "Python")
    role = _create_role(name="Backend Developer")
    python = _create_technology("Python")
    _create_role_skill(role.id, python.id)

    response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 1
    assert data["updated"] == 0
    assert _count_match_results() == 1


def test_calculate_matching_updates_existing_match_results_instead_of_creating_duplicates():
    user = _create_user()
    role = _create_role(name="Backend Developer")
    python = _create_technology("Python")
    _create_role_skill(role.id, python.id)

    first_response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))
    assert first_response.status_code == 200
    first_total_score = first_response.json()["results"][0]["total_score"]

    profile = _create_profile(user.id)
    _create_skill(profile.id, "Python")

    second_response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    assert second_response.status_code == 200
    data = second_response.json()
    assert data["created"] == 0
    assert data["updated"] == 1
    assert _count_match_results() == 1
    assert data["results"][0]["total_score"] > first_total_score


def test_calculate_matching_does_not_duplicate_user_role_pairs():
    user = _create_user()
    profile = _create_profile(user.id)
    _create_skill(profile.id, "Python")
    role = _create_role(name="Backend Developer")
    python = _create_technology("Python")
    _create_role_skill(role.id, python.id)

    client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))
    client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    results = _list_match_results_for_user(user.id)

    assert len(results) == 1
    assert results[0].user_id == user.id
    assert str(results[0].role_id) == str(role.id)


def test_calculate_matching_returns_expected_response_structure():
    user = _create_user()
    profile = _create_profile(user.id)
    _create_skill(profile.id, "Python")
    role = _create_role(name="Backend Developer")
    python = _create_technology("Python")
    _create_role_skill(role.id, python.id)

    response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"processed_roles", "created", "updated", "results"}
    assert set(data["results"][0].keys()) == {
        "role_id",
        "role_name",
        "total_score",
        "breakdown",
        "skill_gaps",
    }


def test_calculate_matching_returns_empty_summary_when_no_roles_are_available():
    user = _create_user()
    _create_role(name="Inactive Backend", active=False)

    response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    assert response.json() == {
        "processed_roles": 0,
        "created": 0,
        "updated": 0,
        "results": [],
    }


def test_calculate_matching_handles_profile_with_insufficient_data_without_breaking():
    user = _create_user()
    role = _create_role(name="Backend Developer")
    python = _create_technology("Python")
    _create_role_skill(role.id, python.id)

    response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    data = response.json()
    assert data["processed_roles"] == 1
    assert data["results"][0]["total_score"] == 0.0
    results = _list_match_results_for_user(user.id)
    assert len(results) == 1
    assert float(results[0].total_score) == 0.0


def test_calculate_matching_uses_calculate_match_score_for_each_role(monkeypatch):
    user = _create_user()
    first_role = _create_role(name="Backend Developer")
    second_role = _create_role(name="Data Analyst")
    calls: list[str] = []

    def fake_calculate_match_score(self, user_id, role_id):
        calls.append(str(role_id))
        return {
            "total_score": 12.34,
            "breakdown": {
                "skill_match": 0.0,
                "experience_match": 0.0,
                "education_match": 0.0,
                "preferences_match": 0.0,
            },
            "skill_gaps": [],
        }

    monkeypatch.setattr(matching_module.MatchingService, "calculate_match_score", fake_calculate_match_score)

    response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    assert set(calls) == {str(first_role.id), str(second_role.id)}
    results = _list_match_results_for_user(user.id)
    assert len(results) == 2
    assert all(float(result.total_score) == 12.34 for result in results)
