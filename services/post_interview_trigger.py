import logging

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from core.config import settings
from models.evaluation import Evaluation, EvaluationStatus
from services.badge_service import BadgeService
from services.metrics_service import UserMetricsService

logger = logging.getLogger(__name__)


def trigger_post_evaluation(
    db: Session,
    user_id: int,
    session_id: int,
    total_questions: int,
) -> None:
    """
    Side-effects that run after an evaluation reaches COMPLETED:
    update user metrics and unlock any newly earned badges.

    Badge unlock only fires once the session is fully answered
    (completed_questions == total_questions).
    """
    UserMetricsService(db).update_for_user(user_id)

    if not settings.ENABLE_BADGES or total_questions <= 0:
        return

    completed_q = (
        db.query(func.count(Evaluation.id))
        .filter(
            Evaluation.interview_session_id == session_id,
            Evaluation.status == EvaluationStatus.COMPLETED,
            Evaluation.score >= 0,
        )
        .scalar()
        or 0
    )

    if completed_q < total_questions:
        return

    session_evals = (
        db.query(Evaluation)
        .filter(
            Evaluation.interview_session_id == session_id,
            Evaluation.status == EvaluationStatus.COMPLETED,
            Evaluation.score >= 0,
        )
        .all()
    )
    valid = [e.score for e in session_evals if e.score is not None]
    session_score = round(sum(valid) / len(valid), 2) if valid else None

    BadgeService(db).check_and_unlock_badges(
        user_id=user_id,
        session_id=session_id,
        session_score=session_score,
    )
