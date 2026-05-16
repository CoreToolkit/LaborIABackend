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
        self._metrics = UserMetricsService(db)

    def get_user_badges_with_progress(self, user_id: int) -> list[dict]:
        """
        Returns all badges with unlock status and progress (0.0–1.0) toward each condition.
        Used by GET /api/badges/me.
        """
        total_interviews = self._count_completed_sessions(user_id)
        avg_score = self._metrics.calculate_average_score(user_id)
        best_session_score = self._get_best_session_score(user_id)
        best_improvement = self._get_best_score_improvement(user_id)

        unlocked_ids = {ub.badge_id for ub in self.repo.list_by_user(user_id)}

        result = []
        for badge in self.repo.list_all():
            is_unlocked = badge.id in unlocked_ids
            progress = self._calculate_progress(badge, {
                "total_interviews": total_interviews,
                "avg_score": avg_score,
                "best_session_score": best_session_score,
                "best_improvement": best_improvement,
            })
            result.append({
                "id": badge.id,
                "name": badge.name,
                "description": badge.description,
                "icon": badge.icon,
                "condition_type": badge.condition_type,
                "condition_value": badge.condition_value,
                "is_unlocked": is_unlocked,
                "progress": progress,
            })

        return result

    def _calculate_progress(self, badge: Badge, context: dict) -> float:
        t = badge.condition_type
        v = badge.condition_value
        if not t or not v:
            return 0.0
        try:
            if t == "total_interviews":
                return min(context["total_interviews"] / int(v), 1.0)
            if t == "session_score_gte":
                score = context["best_session_score"]
                return min(score / float(v), 1.0) if score is not None else 0.0
            if t == "score_improvement_gte":
                improvement = context["best_improvement"]
                return min(improvement / float(v), 1.0) if improvement is not None else 0.0
            if t == "avg_score_gte":
                return min(context["avg_score"] / float(v), 1.0)
        except (ValueError, TypeError, ZeroDivisionError):
            pass
        return 0.0

    def _get_best_session_score(self, user_id: int) -> float | None:
        from models.evaluation import Evaluation, EvaluationStatus
        from models.interview_session import InterviewSession

        # Una sola query: obtener todos los session_ids con su score promedio.
        # Evita N+1: en lugar de N sesiones + N queries de evaluaciones, 
        # una sola query con join y group_by.
        rows = (
            self.db.query(
                InterviewSession.id,
                sqlfunc.avg(Evaluation.score).label('avg_score')
            )
            .join(Evaluation, Evaluation.interview_session_id == InterviewSession.id)
            .filter(
                InterviewSession.user_id == user_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
                Evaluation.score >= 0,
            )
            .group_by(InterviewSession.id)
            .all()
        )
        
        if not rows:
            return None
        
        # Retorna el máximo promedio de todas las sesiones
        best = max(row.avg_score for row in rows if row.avg_score is not None)
        return round(best, 2) if best is not None else None

    def _get_best_score_improvement(self, user_id: int) -> float | None:
        from models.evaluation import Evaluation, EvaluationStatus
        from models.interview_session import InterviewSession

        # Una sola query: obtener todas las sesiones del usuario con su score promedio,
        # ordenadas por fecha. Evita N+1 (N sesiones + N queries de evaluaciones).
        rows = (
            self.db.query(
                InterviewSession.id,
                InterviewSession.created_at,
                sqlfunc.avg(Evaluation.score).label('avg_score')
            )
            .join(Evaluation, Evaluation.interview_session_id == InterviewSession.id)
            .filter(
                InterviewSession.user_id == user_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
                Evaluation.score >= 0,
            )
            .group_by(InterviewSession.id, InterviewSession.created_at)
            .order_by(InterviewSession.created_at.asc())
            .all()
        )

        if len(rows) < 2:
            return None
        
        # Calcular mejora máxima entre sesiones consecutivas
        scores = [row.avg_score for row in rows if row.avg_score is not None]
        if len(scores) < 2:
            return None
        
        best_improvement: float | None = None
        for i in range(1, len(scores)):
            diff = scores[i] - scores[i - 1]
            if best_improvement is None or diff > best_improvement:
                best_improvement = diff
        
        return round(best_improvement, 2) if best_improvement is not None else None

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
        avg_score = self._metrics.calculate_average_score(user_id)

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
        return self._metrics._count_completed_interviews(user_id)

    def _get_previous_session_score(self, user_id: int, current_session_id: int) -> float | None:
        from models.evaluation import Evaluation, EvaluationStatus
        from models.interview_session import InterviewSession

        row = (
            self.db.query(
                InterviewSession.id,
                sqlfunc.avg(Evaluation.score).label("avg_score"),
            )
            .join(Evaluation, Evaluation.interview_session_id == InterviewSession.id)
            .filter(
                InterviewSession.user_id == user_id,
                InterviewSession.id != current_session_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
                Evaluation.score >= 0,
            )
            .group_by(InterviewSession.id, InterviewSession.created_at)
            .order_by(InterviewSession.created_at.desc())
            .first()
        )

        if not row or row.avg_score is None:
            return None

        return round(float(row.avg_score), 2)
