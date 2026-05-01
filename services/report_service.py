from sqlalchemy.orm import Session, joinedload

from models.evaluation import Evaluation, EvaluationStatus
from models.interview_session import InterviewSession
from services.badge_service import BadgeService


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def get_session_report(self, session_id: int, user_id: int) -> dict | None:
        session = self._get_session(session_id, user_id)
        if not session:
            return None

        return self._build_session_report(session=session, user_id=user_id, unlock_badges=True)

    def list_session_reports(self, user_id: int) -> list[dict]:
        sessions = (
            self.db.query(InterviewSession)
            .options(joinedload(InterviewSession.questions))
            .filter(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
            .all()
        )

        return [
            self._build_session_report(session=session, user_id=user_id, unlock_badges=False)
            for session in sessions
        ]

    def list_session_reports_summary(self, user_id: int) -> list[dict]:
        """
        Retorna una versión ligera de los reportes del usuario, adecuada para listados
        y tarjetas en el frontend. No provoca side-effects.
        """
        full_reports = self.list_session_reports(user_id=user_id)
        summaries = []
        for r in full_reports:
            summaries.append(
                {
                    "session_id": r["session_id"],
                    "session_score": r["session_score"],
                    "session_created_at": r["session_created_at"],
                    "total_questions": r["total_questions"],
                    "completed_questions": r["completed_questions"],
                    "trend": r["comparison"]["trend"],
                    "improvement": r["comparison"]["improvement"],
                    "previous_score": r["comparison"]["previous_score"],
                    "badges_count": len(r.get("badges_unlocked", [])),
                }
            )

        return summaries

    def _build_session_report(
        self,
        session: InterviewSession,
        user_id: int,
        unlock_badges: bool,
    ) -> dict:

        evaluations = self._get_session_evaluations(session.id)
        session_score = self._calculate_session_score(evaluations)

        if unlock_badges:
            BadgeService(self.db).check_and_unlock_badges(
                user_id=user_id,
                session_id=session.id,
                session_score=session_score,
            )

        comparison = self._get_comparison(user_id, session.id, session_score)
        badges = self._get_session_badges(user_id, session.created_at)

        return {
            "session_id": session.id,
            "session_score": session_score,
            "total_questions": len(session.questions),
            "completed_questions": len(evaluations),
            "evaluations": [self._format_evaluation(e) for e in evaluations],
            "comparison": comparison,
            "badges_unlocked": badges,
            "session_created_at": str(session.created_at),
        }

    # ── privados ──────────────────────────────────────────────────────────────

    def _get_session(self, session_id: int, user_id: int) -> InterviewSession | None:
        return (
            self.db.query(InterviewSession)
            .options(joinedload(InterviewSession.questions))
            .filter(
                InterviewSession.id == session_id,
                InterviewSession.user_id == user_id,
            )
            .first()
        )

    def _get_session_evaluations(self, session_id: int) -> list[Evaluation]:
        return (
            self.db.query(Evaluation)
            .options(joinedload(Evaluation.question))
            .filter(
                Evaluation.interview_session_id == session_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
                Evaluation.score >= 0,
            )
            .all()
        )

    def _calculate_session_score(self, evaluations: list[Evaluation]) -> float | None:
        valid = [e.score for e in evaluations if e.score is not None and e.score >= 0]
        if not valid:
            return None
        return round(sum(valid) / len(valid), 2)

    def _get_comparison(
        self, user_id: int, session_id: int, session_score: float | None
    ) -> dict:
        prev_sessions = (
            self.db.query(InterviewSession)
            .filter(
                InterviewSession.user_id == user_id,
                InterviewSession.id != session_id,
            )
            .order_by(InterviewSession.created_at.desc())
            .all()
        )

        for prev in prev_sessions:
            prev_evals = self._get_session_evaluations(prev.id)
            prev_score = self._calculate_session_score(prev_evals)
            if prev_score is None:
                continue

            improvement = None
            trend = "stable"
            if session_score is not None:
                improvement = round(session_score - prev_score, 2)
                if improvement > 0:
                    trend = "improved"
                elif improvement < 0:
                    trend = "declined"

            return {
                "has_previous": True,
                "previous_session_id": prev.id,
                "previous_score": prev_score,
                "improvement": improvement,
                "trend": trend,
            }

        return {
            "has_previous": False,
            "previous_session_id": None,
            "previous_score": None,
            "improvement": None,
            "trend": "first_session",
        }

    def _get_session_badges(self, user_id: int, session_created_at) -> list[dict]:
        from repositories.badge_repository import BadgeRepository

        user_badges = BadgeRepository(self.db).list_by_user_since(user_id, session_created_at)
        return [
            {
                "id": ub.badge.id,
                "name": ub.badge.name,
                "description": ub.badge.description,
                "icon": ub.badge.icon,
            }
            for ub in user_badges
            if ub.badge is not None
        ]

    def _format_evaluation(self, evaluation: Evaluation) -> dict:
        q = evaluation.question
        return {
            "evaluation_id": str(evaluation.id),
            "question_text": q.question_text if q else None,
            "category": q.category if q else None,
            "difficulty": q.difficulty if q else None,
            "score": evaluation.score,
            "feedback": evaluation.feedback,
            "score_breakdown": evaluation.score_breakdown or {},
            "topics_covered": evaluation.topics_covered or [],
            "topics_missing": evaluation.topics_missing or [],
        }
