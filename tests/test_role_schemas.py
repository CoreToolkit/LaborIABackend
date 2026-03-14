from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from models.job_role import JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from schemas.role import RoleCreateSchema, RoleDetailSchema, RoleResponseSchema


def test_role_create_schema_accepts_valid_payload():
    payload = {
        "name": "Backend Developer",
        "description": "Builds backend services",
        "category": "tech",
        "seniority_level": "junior",
        "min_english_level": "B1",
        "estimated_salary_min_cop": "3000000",
        "estimated_salary_max_cop": "5000000",
        "role_skills": [
            {
                "technology_id": 1,
                "importance_weight": 8,
                "is_required": True,
            }
        ],
    }

    schema = RoleCreateSchema.model_validate(payload)

    assert schema.category == JobRoleCategory.TECH
    assert schema.seniority_level == SeniorityLevel.JUNIOR
    assert schema.min_english_level == RoleEnglishLevel.B1
    assert schema.role_skills[0].importance_weight == 8
    assert schema.active is True


def test_role_create_schema_rejects_invalid_salary_range():
    with pytest.raises(ValidationError):
        RoleCreateSchema.model_validate(
            {
                "name": "Backend Developer",
                "category": "tech",
                "seniority_level": "junior",
                "min_english_level": "B1",
                "estimated_salary_min_cop": "6000000",
                "estimated_salary_max_cop": "5000000",
            }
        )


def test_role_create_schema_rejects_invalid_importance_weight():
    with pytest.raises(ValidationError):
        RoleCreateSchema.model_validate(
            {
                "name": "Backend Developer",
                "category": "tech",
                "seniority_level": "junior",
                "min_english_level": "B1",
                "role_skills": [
                    {
                        "technology_id": 1,
                        "importance_weight": 11,
                    }
                ],
            }
        )


def test_role_response_schema_serializes_role_summary():
    role = SimpleNamespace(
        id=uuid4(),
        name="Backend Developer",
        category=JobRoleCategory.TECH,
        seniority_level=SeniorityLevel.MID,
        min_english_level=RoleEnglishLevel.B2,
        estimated_salary_min_cop=Decimal("4000000"),
        estimated_salary_max_cop=Decimal("7000000"),
        active=True,
    )

    payload = RoleResponseSchema.model_validate(role).model_dump(mode="json")

    assert payload["name"] == "Backend Developer"
    assert payload["category"] == "tech"
    assert payload["seniority_level"] == "mid"
    assert payload["min_english_level"] == "B2"


def test_role_detail_schema_serializes_nested_requirements():
    detail = SimpleNamespace(
        id=uuid4(),
        name="Backend Developer",
        description="Builds backend services",
        category=JobRoleCategory.TECH,
        seniority_level=SeniorityLevel.SENIOR,
        min_english_level=RoleEnglishLevel.C1,
        estimated_salary_min_cop=Decimal("7000000"),
        estimated_salary_max_cop=Decimal("9000000"),
        active=True,
        created_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
        role_skills=[
            SimpleNamespace(
                id=1,
                technology_id=10,
                technology=SimpleNamespace(name="FastAPI"),
                importance_weight=9,
                is_required=True,
            )
        ],
    )

    payload = RoleDetailSchema.model_validate(detail).model_dump(mode="json")

    assert payload["description"] == "Builds backend services"
    assert payload["role_skills"][0]["technology_name"] == "FastAPI"
    assert payload["role_skills"][0]["importance_weight"] == 9
