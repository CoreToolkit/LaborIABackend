# tests/test_models_stage1.py
# Tests for Etapa 1: UserMetrics, Recommendation, Badge, UserBadge models.

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.user import User
from models.job_role import JobRole, JobRoleCategory, SeniorityLevel, RoleEnglishLevel
from models.user_metrics import UserMetrics
from models.recommendation import Recommendation
from models.badge import Badge, UserBadge

import uuid


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def sample_user(db_session):
    user = User(email="test@example.com", name="Test User", oauth_provider="google")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def sample_role(db_session):
    role = JobRole(
        id=uuid.uuid4(),
        name="Backend Developer",
        category=JobRoleCategory.TECH,
        seniority_level=SeniorityLevel.MID,
        min_english_level=RoleEnglishLevel.B1,
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


# ── UserMetrics ───────────────────────────────────────────────────────────────

class TestUserMetrics:
    def test_create_user_metrics(self, db_session, sample_user):
        metrics = UserMetrics(
            user_id=sample_user.id,
            total_interviews=5,
            avg_score=78.50,
            score_by_skill={"python": 85.0, "sql": 72.0},
        )
        db_session.add(metrics)
        db_session.commit()
        db_session.refresh(metrics)

        assert metrics.id is not None
        assert metrics.user_id == sample_user.id
        assert metrics.total_interviews == 5
        assert float(metrics.avg_score) == 78.50
        assert metrics.last_updated is not None

    def test_update_json_field(self, db_session, sample_user):
        metrics = db_session.query(UserMetrics).filter_by(user_id=sample_user.id).first()
        assert metrics is not None

        metrics.score_by_skill = {"python": 90.0, "sql": 80.0, "docker": 65.0}
        db_session.commit()
        db_session.refresh(metrics)

        assert metrics.score_by_skill["docker"] == 65.0
        assert len(metrics.score_by_skill) == 3

    def test_user_metrics_unique_per_user(self, db_session, sample_user):
        duplicate = UserMetrics(user_id=sample_user.id, total_interviews=1)
        db_session.add(duplicate)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()


# ── Recommendation ────────────────────────────────────────────────────────────

class TestRecommendation:
    def test_create_recommendation_with_role(self, db_session, sample_user, sample_role):
        rec = Recommendation(
            user_id=sample_user.id,
            role_id=sample_role.id,
            priority=1,
            reason="Strong match in backend skills.",
        )
        db_session.add(rec)
        db_session.commit()
        db_session.refresh(rec)

        assert rec.id is not None
        assert rec.user_id == sample_user.id
        assert rec.role_id == sample_role.id
        assert rec.priority == 1
        assert rec.created_at is not None

    def test_create_recommendation_without_role(self, db_session, sample_user):
        rec = Recommendation(
            user_id=sample_user.id,
            role_id=None,
            priority=0,
            reason="General improvement recommendation.",
        )
        db_session.add(rec)
        db_session.commit()
        db_session.refresh(rec)

        assert rec.id is not None
        assert rec.role_id is None

    def test_query_recommendations_by_user(self, db_session, sample_user):
        recs = db_session.query(Recommendation).filter_by(user_id=sample_user.id).all()
        assert len(recs) >= 2


# ── Badge + UserBadge ─────────────────────────────────────────────────────────

class TestBadgeAndUserBadge:
    def test_create_badge(self, db_session):
        badge = Badge(
            name="First Interview",
            description="Completed your first interview.",
            icon="star",
            condition_type="interview_count",
            condition_value="1",
        )
        db_session.add(badge)
        db_session.commit()
        db_session.refresh(badge)

        assert badge.id is not None
        assert badge.name == "First Interview"
        assert badge.condition_type == "interview_count"

    def test_assign_badge_to_user(self, db_session, sample_user):
        badge = db_session.query(Badge).filter_by(name="First Interview").first()
        user_badge = UserBadge(user_id=sample_user.id, badge_id=badge.id)
        db_session.add(user_badge)
        db_session.commit()
        db_session.refresh(user_badge)

        assert user_badge.id is not None
        assert user_badge.user_id == sample_user.id
        assert user_badge.badge_id == badge.id
        assert user_badge.unlocked_at is not None

    def test_duplicate_badge_raises_error(self, db_session, sample_user):
        badge = db_session.query(Badge).filter_by(name="First Interview").first()
        duplicate = UserBadge(user_id=sample_user.id, badge_id=badge.id)
        db_session.add(duplicate)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_user_relationship_loads_badges(self, db_session, sample_user):
        db_session.refresh(sample_user)
        assert len(sample_user.user_badges) >= 1
        assert sample_user.user_badges[0].badge.name == "First Interview"
