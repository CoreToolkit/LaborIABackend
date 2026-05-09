from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session, joinedload

from models.evaluation import Evaluation, EvaluationStatus
from models.interview_session import InterviewSession
from models.badge import UserBadge
from models.question import Question
from services.badge_service import BadgeService


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def get_session_report(
        self,
        session_id: int,
        user_id: int,
        unlock_badges: bool = False,
    ) -> dict | None:
        session = self._get_session(session_id, user_id)
        if not session:
            return None

        return self._build_session_report(
            session=session,
            user_id=user_id,
            unlock_badges=unlock_badges,
        )

    def list_session_reports(
        self,
        user_id: int,
        limit: int = 3,
        offset: int = 0,
    ) -> list[dict]:
        sessions = (
            self.db.query(InterviewSession)
            .options(joinedload(InterviewSession.questions))
            .filter(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
            .offset(offset)
            .limit(limit)
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
        question_counts = (
            self.db.query(
                Question.interview_session_id.label("session_id"),
                sqlfunc.count(Question.id).label("total_questions"),
            )
            .group_by(Question.interview_session_id)
            .subquery()
        )
        evaluation_scores = (
            self.db.query(
                Evaluation.interview_session_id.label("session_id"),
                sqlfunc.count(Evaluation.id).label("completed_questions"),
                sqlfunc.avg(Evaluation.score).label("session_score"),
            )
            .filter(
                Evaluation.status == EvaluationStatus.COMPLETED,
                Evaluation.score >= 0,
            )
            .group_by(Evaluation.interview_session_id)
            .subquery()
        )

        rows = (
            self.db.query(
                InterviewSession.id.label("session_id"),
                InterviewSession.created_at.label("session_created_at"),
                sqlfunc.coalesce(question_counts.c.total_questions, 0).label("total_questions"),
                sqlfunc.coalesce(evaluation_scores.c.completed_questions, 0).label("completed_questions"),
                evaluation_scores.c.session_score.label("session_score"),
            )
            .outerjoin(question_counts, question_counts.c.session_id == InterviewSession.id)
            .outerjoin(evaluation_scores, evaluation_scores.c.session_id == InterviewSession.id)
            .filter(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.asc(), InterviewSession.id.asc())
            .all()
        )
        badge_unlock_times = [
            item[0]
            for item in (
                self.db.query(UserBadge.unlocked_at)
                .filter(UserBadge.user_id == user_id)
                .all()
            )
        ]

        summaries = []
        previous_score = None
        for row in rows:
            session_score = round(row.session_score, 2) if row.session_score is not None else None
            improvement = None
            trend = "first_session" if previous_score is None else "stable"
            if previous_score is not None and session_score is not None:
                improvement = round(session_score - previous_score, 2)
                if improvement > 0:
                    trend = "improved"
                elif improvement < 0:
                    trend = "declined"

            badges_count = sum(
                1
                for unlocked_at in badge_unlock_times
                if unlocked_at and unlocked_at >= row.session_created_at
            )

            summaries.append(
                {
                    "session_id": row.session_id,
                    "session_score": session_score,
                    "session_created_at": str(row.session_created_at),
                    "total_questions": int(row.total_questions or 0),
                    "completed_questions": int(row.completed_questions or 0),
                    "trend": trend,
                    "improvement": improvement,
                    "previous_score": previous_score,
                    "badges_count": int(badges_count),
                }
            )
            if session_score is not None:
                previous_score = session_score

        return list(reversed(summaries))

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
        from sqlalchemy import func as sqlfunc
        
        # Una sola query: obtener sesión previa más reciente con su score promedio.
        # Evita N+1: en lugar de traer todas las sesiones (N queries), 
        # traemos solo la más reciente con su score agregado (1 query).
        prev_row = (
            self.db.query(
                InterviewSession.id,
                sqlfunc.avg(Evaluation.score).label('prev_score')
            )
            .join(Evaluation, Evaluation.interview_session_id == InterviewSession.id)
            .filter(
                InterviewSession.user_id == user_id,
                InterviewSession.id != session_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
                Evaluation.score >= 0,
            )
            .group_by(InterviewSession.id)
            .order_by(InterviewSession.created_at.desc())
            .first()
        )

        if not prev_row or prev_row.prev_score is None:
            return {
                "has_previous": False,
                "previous_session_id": None,
                "previous_score": None,
                "improvement": None,
                "trend": "first_session",
            }

        prev_score = round(prev_row.prev_score, 2)
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
            "previous_session_id": prev_row.id,
            "previous_score": prev_score,
            "improvement": improvement,
            "trend": trend,
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
