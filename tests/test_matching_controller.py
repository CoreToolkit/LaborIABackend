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


def _create_match_result(user_id: int, role_id, total_score: Decimal | str | float) -> MatchResult:
    db = TestSessionLocal()
    try:
        match_result = MatchResult(
            user_id=user_id,
            role_id=role_id,
            total_score=Decimal(str(total_score)),
        )
        db.add(match_result)
        db.commit()
        db.refresh(match_result)
        return match_result
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

    assert response.status_code in {401, 403}


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


def test_calculate_matching_delegates_to_bulk_matching_service(monkeypatch):
    user = _create_user()
    calls: list[int] = []
    fake_role_id = str(uuid.uuid4())

    def fake_calculate_and_cache_matches_for_user(self, user_id):
        calls.append(user_id)
        return {
            "processed_roles": 2,
            "created": 1,
            "updated": 1,
            "results": [
                {
                    "role_id": fake_role_id,
                    "role_name": "Backend Developer",
                    "total_score": 12.34,
                    "breakdown": {
                        "skill_match": 0.0,
                        "experience_match": 0.0,
                        "education_match": 0.0,
                        "preferences_match": 0.0,
                    },
                    "skill_gaps": [],
                }
            ],
        }

    monkeypatch.setattr(
        matching_module.MatchingService,
        "calculate_and_cache_matches_for_user",
        fake_calculate_and_cache_matches_for_user,
    )

    response = client.post("/api/matching/calculate", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    assert calls == [user.id]
    assert response.json() == {
        "processed_roles": 2,
        "created": 1,
        "updated": 1,
        "results": [
            {
                "role_id": fake_role_id,
                "role_name": "Backend Developer",
                "total_score": 12.34,
                "breakdown": {
                    "skill_match": 0.0,
                    "experience_match": 0.0,
                    "education_match": 0.0,
                    "preferences_match": 0.0,
                },
                "skill_gaps": [],
            }
        ],
    }


def test_get_matching_recommendations_returns_200_for_authenticated_user():
    user = _create_user()
    role = _create_role(name="Backend Developer")
    _create_match_result(user.id, role.id, "82.50")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200


def test_get_matching_recommendations_requires_authentication():
    response = client.get("/api/matching/recommendations")

    assert response.status_code in {401, 403}


def test_get_matching_recommendations_returns_maximum_ten_results_sorted_descending():
    user = _create_user()

    for index in range(12):
        role = _create_role(name=f"Role {index:02d}")
        _create_match_result(user.id, role.id, Decimal(100 - index))

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["recommendations"]) == 10
    returned_scores = [item["total_score"] for item in data["recommendations"]]
    assert returned_scores == sorted(returned_scores, reverse=True)
    assert returned_scores[0] == 100.0
    assert returned_scores[-1] == 91.0


def test_get_matching_recommendations_filters_only_current_user_results():
    current_user = _create_user()
    other_user = _create_user()
    current_user_role = _create_role(name="Current User Role")
    other_user_role = _create_role(name="Other User Role")
    _create_match_result(current_user.id, current_user_role.id, "77.70")
    _create_match_result(other_user.id, other_user_role.id, "99.90")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(current_user))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["recommendations"][0]["role_name"] == "Current User Role"
    assert data["recommendations"][0]["total_score"] == 77.7


def test_get_matching_recommendations_excludes_inactive_roles_from_cache():
    user = _create_user()
    active_role = _create_role(name="Active Role", active=True)
    inactive_role = _create_role(name="Inactive Role", active=False)
    _create_match_result(user.id, active_role.id, "80.00")
    _create_match_result(user.id, inactive_role.id, "95.00")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["recommendations"][0]["role_name"] == "Active Role"
    assert data["recommendations"][0]["total_score"] == 80.0


def test_get_matching_recommendations_returns_empty_list_when_user_has_no_cache():
    user = _create_user()
    _create_role(name="Backend Developer")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    assert response.json() == {
        "recommendations": [],
        "total": 0,
    }


def test_get_matching_recommendations_does_not_recalculate_matching(monkeypatch):
    user = _create_user()
    role = _create_role(name="Backend Developer")
    _create_match_result(user.id, role.id, "80.00")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("calculate_match_score should not be called")

    monkeypatch.setattr(matching_module.MatchingService, "calculate_match_score", fail_if_called)

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["recommendations"][0]["total_score"] == 80.0


def test_get_matching_recommendations_returns_expected_response_structure():
    user = _create_user()
    role = _create_role(name="Backend Developer")
    _create_match_result(user.id, role.id, "88.80")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"recommendations", "total"}
    assert set(data["recommendations"][0].keys()) == {
        "role_id",
        "role_name",
        "total_score",
        "category",
        "seniority_level",
        "min_english_level",
        "estimated_salary_min_cop",
        "estimated_salary_max_cop",
        "active",
        "skill_gaps",
        "reason",
    }


def test_get_matching_recommendations_includes_basic_role_information():
    user = _create_user()
    role = _create_role(
        name="Backend Developer",
        salary_min=Decimal("4000000"),
        salary_max=Decimal("6500000"),
    )
    _create_match_result(user.id, role.id, "91.25")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    item = response.json()["recommendations"][0]
    assert item["role_id"] == str(role.id)
    assert item["role_name"] == "Backend Developer"
    assert item["total_score"] == 91.25
    assert item["category"] == "tech"
    assert item["seniority_level"] == "mid"
    assert item["min_english_level"] == "B2"
    assert item["estimated_salary_min_cop"] == "4000000.00"
    assert item["estimated_salary_max_cop"] == "6500000.00"
    assert item["active"] is True


def test_get_matching_recommendations_includes_skill_gaps_and_reason():
    """TASK-027-06: skill_gaps y reason aparecen en cada recomendación."""
    user = _create_user()
    role = _create_role(name="DevOps Engineer")
    _create_match_result(user.id, role.id, "75.00")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    item = response.json()["recommendations"][0]
    assert "skill_gaps" in item
    assert "reason" in item
    assert isinstance(item["skill_gaps"], list)
    assert isinstance(item["reason"], str)
    assert len(item["reason"]) > 0


def test_get_matching_recommendations_skill_gaps_max_3():
    """skill_gaps retorna máximo 3 items."""
    user = _create_user()
    role = _create_role(name="Full Stack Developer")

    # Crear 5 tecnologías requeridas que el usuario no tiene
    for i in range(5):
        tech = _create_technology(f"Tech{i}-{uuid.uuid4().hex[:4]}")
        _create_role_skill(role.id, tech.id, importance_weight=10 - i)

    _create_match_result(user.id, role.id, "30.00")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    item = response.json()["recommendations"][0]
    assert len(item["skill_gaps"]) <= 3


def test_get_matching_recommendations_skill_gaps_structure():
    """Cada skill_gap tiene name e importance_weight."""
    user = _create_user()
    role = _create_role(name="Backend Developer")
    tech = _create_technology(f"Python-{uuid.uuid4().hex[:4]}")
    _create_role_skill(role.id, tech.id, importance_weight=8)
    _create_match_result(user.id, role.id, "50.00")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    item = response.json()["recommendations"][0]
    if item["skill_gaps"]:
        gap = item["skill_gaps"][0]
        assert "name" in gap
        assert "importance_weight" in gap


def test_get_matching_recommendations_reason_contains_role_name():
    """reason incluye el nombre del rol (fallback genérico)."""
    user = _create_user()
    role = _create_role(name="Data Scientist")
    _create_match_result(user.id, role.id, "68.00")

    response = client.get("/api/matching/recommendations", headers=_auth_headers_for_user(user))

    assert response.status_code == 200
    item = response.json()["recommendations"][0]
    assert "Data Scientist" in item["reason"]
