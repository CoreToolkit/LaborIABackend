import uuid
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy.exc import IntegrityError

from core.database import Base, engine, SessionLocal
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.match_result import MatchResult
from models.user import User


Base.metadata.create_all(bind=engine)


def _create_user(db) -> User:
    user = User(
        email=f"match-result-{uuid.uuid4().hex}@example.com",
        name="Match Result User",
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
        name=f"Backend Developer {uuid.uuid4().hex}",
        description="Builds APIs",
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


def test_match_result_persist_and_relationships():
    db = SessionLocal()
    try:
        user = _create_user(db)
        role = _create_role(db)

        match_result = MatchResult(
            user_id=user.id,
            role_id=role.id,
            total_score=Decimal("82.50"),
        )
        db.add(match_result)
        db.commit()
        db.refresh(match_result)

        assert match_result.id is not None
        assert match_result.created_at is not None
        assert match_result.updated_at is not None
        assert match_result.user.id == user.id
        assert match_result.job_role.id == role.id
    finally:
        db.close()


def test_match_result_enforces_unique_user_role_pair():
    db = SessionLocal()
    try:
        user = _create_user(db)
        role = _create_role(db)

        db.add(
            MatchResult(
                user_id=user.id,
                role_id=role.id,
                total_score=Decimal("75.00"),
            )
        )
        db.commit()

        db.add(
            MatchResult(
                user_id=user.id,
                role_id=role.id,
                total_score=Decimal("90.00"),
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()
