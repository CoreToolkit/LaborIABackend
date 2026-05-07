import logging

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from models.badge import Badge
from repositories.badge_repository import BadgeRepository
from services.metrics_service import UserMetricsService

logger = logging.getLogger(__name__)


class BadgeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BadgeRepository(db)

    def check_and_unlock_badges(
        self,
        user_id: int,
        session_id: int,
        session_score: float | None = None,
    ) -> list[Badge]:
        """
        Evalúa todas las condiciones de badge para el usuario tras completar una sesión.
        Idempotente: nunca desbloquea un badge que el usuario ya tiene.
        Retorna la lista de badges recién desbloqueados.
        """
        total_interviews = self._count_completed_sessions(user_id)
        previous_score = self._get_previous_session_score(user_id, session_id)
        avg_score = UserMetricsService(self.db).calculate_average_score(user_id)

        context = {
            "session_score": session_score,
            "previous_score": previous_score,
            "total_interviews": total_interviews,
            "avg_score": avg_score,
        }

        all_badges = self.repo.list_all()
        unlocked_ids = {ub.badge_id for ub in self.repo.list_by_user(user_id)}

        newly_unlocked: list[Badge] = []
        for badge in all_badges:
            if badge.id in unlocked_ids:
                continue
            if self._meets_condition(badge, context):
                try:
                    self.repo.unlock_badge(user_id, badge.id)
                    newly_unlocked.append(badge)
                except Exception:
                    logger.warning(
                        "badge_service: badge already unlocked (race condition) user=%s badge=%s",
                        user_id, badge.id,
                    )

        if newly_unlocked:
            self.db.commit()

        return newly_unlocked

    def _meets_condition(self, badge: Badge, context: dict) -> bool:
        t = badge.condition_type
        v = badge.condition_value
        if not t or not v:
            return False
        try:
            if t == "total_interviews":
                return context["total_interviews"] >= int(v)
            if t == "session_score_gte":
                score = context["session_score"]
                return score is not None and score >= float(v)
            if t == "score_improvement_gte":
                curr = context["session_score"]
                prev = context["previous_score"]
                return curr is not None and prev is not None and (curr - prev) >= float(v)
            if t == "avg_score_gte":
                return context["avg_score"] >= float(v)
        except (ValueError, TypeError):
            pass
        return False

    def _count_completed_sessions(self, user_id: int) -> int:
        from models.evaluation import Evaluation, EvaluationStatus
        from models.interview_session import InterviewSession

        return (
            self.db.query(sqlfunc.count(sqlfunc.distinct(Evaluation.interview_session_id)))
            .join(InterviewSession, Evaluation.interview_session_id == InterviewSession.id)
            .filter(
                InterviewSession.user_id == user_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
            )
            .scalar()
            or 0
        )

    def _get_previous_session_score(self, user_id: int, current_session_id: int) -> float | None:
        from models.evaluation import Evaluation, EvaluationStatus
        from models.interview_session import InterviewSession

        prev_sessions = (
            self.db.query(InterviewSession)
            .filter(
                InterviewSession.user_id == user_id,
                InterviewSession.id != current_session_id,
            )
            .order_by(InterviewSession.created_at.desc())
            .all()
        )

        for session in prev_sessions:
            evals = (
                self.db.query(Evaluation)
                .filter(
                    Evaluation.interview_session_id == session.id,
                    Evaluation.status == EvaluationStatus.COMPLETED,
                    Evaluation.score >= 0,
                )
                .all()
            )
            valid = [e.score for e in evals if e.score is not None]
            if valid:
                return round(sum(valid) / len(valid), 2)

        return None
