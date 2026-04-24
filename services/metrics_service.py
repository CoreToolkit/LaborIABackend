# services/metrics_service.py
# ─────────────────────────────────────────────────────────────────────────────
# UserMetricsService: calcula métricas de rendimiento del usuario a partir
# de sus evaluaciones completadas.
#
# MÉTODOS:
#   calculate_average_score(user_id)  → float (0.0 si no hay evaluaciones)
#   score_by_category(user_id)        → dict[str, float] por categoría de skill
#   analyze_weak_areas(user_id, ...)  → list[dict] con skills bajo umbral
#
# JOIN PATH para todas las queries:
#   Evaluation → InterviewSession (filter user_id) → Question (category)
#   Solo evaluaciones con status=COMPLETED y score >= 0
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session, joinedload

from models.evaluation import Evaluation, EvaluationStatus
from models.interview_session import InterviewSession
from models.question import Question


class UserMetricsService:
    def __init__(self, db: Session):
        self.db = db

    def _get_completed_evaluations(self, user_id: int) -> list[Evaluation]:
        """Retorna evaluaciones completadas con score válido (>= 0) del usuario."""
        return (
            self.db.query(Evaluation)
            .options(joinedload(Evaluation.question))
            .join(InterviewSession, Evaluation.interview_session_id == InterviewSession.id)
            .filter(
                InterviewSession.user_id == user_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
                Evaluation.score >= 0,
            )
            .all()
        )

    def _count_completed_interviews(self, user_id: int) -> int:
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

    def calculate_average_score(self, user_id: int) -> float:
        """
        Calcula el score promedio del usuario sobre evaluaciones completadas.
        Excluye score=-1 (fallo técnico). Retorna 0.0 si no hay evaluaciones.
        """
        evaluations = self._get_completed_evaluations(user_id)
        if not evaluations:
            return 0.0
        valid_scores = [e.score for e in evaluations if e.score is not None and e.score >= 0]
        if not valid_scores:
            return 0.0
        return round(sum(valid_scores) / len(valid_scores), 2)

    def score_by_category(self, user_id: int) -> dict[str, float]:
        """
        Agrupa scores por categoría de skill usando score_breakdown de cada evaluación.
        Retorna { category: avg_score } para cada categoría con al menos una evaluación.
        Ignora evaluaciones sin score_breakdown o con score_breakdown vacío.

        Las categorías vienen del campo score_breakdown de Evaluation:
        {"correctness": 80, "completeness": 70, "clarity": 75, "examples": 60}
        """
        evaluations = self._get_completed_evaluations(user_id)
        if not evaluations:
            return {}

        category_scores: dict[str, list[float]] = defaultdict(list)

        for evaluation in evaluations:
            breakdown = evaluation.score_breakdown
            if not breakdown or not isinstance(breakdown, dict):
                continue
            for category, score in breakdown.items():
                if score is not None:
                    category_scores[category].append(float(score))

        return {
            category: round(sum(scores) / len(scores), 2)
            for category, scores in category_scores.items()
            if scores
        }

    def score_by_skill(self, user_id: int) -> dict[str, float]:
        """
        Agrupa el score promedio por skill individual usando Question.category.
        Retorna { skill: avg_score } para cada skill con al menos una evaluación.
        """
        evaluations = self._get_completed_evaluations(user_id)
        if not evaluations:
            return {}

        skill_scores: dict[str, list[float]] = defaultdict(list)

        for evaluation in evaluations:
            skill = getattr(evaluation.question, "category", None)
            if not skill:
                continue
            if evaluation.score is None or evaluation.score < 0:
                continue
            skill_scores[str(skill)].append(float(evaluation.score))

        return {
            skill: round(sum(scores) / len(scores), 2)
            for skill, scores in skill_scores.items()
            if scores
        }

    def update_for_user(self, user_id: int):
        """
        Recalcula y persiste las métricas agregadas del usuario.

        Retorna el registro UserMetrics actualizado o creado.
        """
        from models.user_metrics import UserMetrics

        avg_score = self.calculate_average_score(user_id)
        score_by_skill = self.score_by_skill(user_id)
        total_interviews = self._count_completed_interviews(user_id)

        metrics = self.db.query(UserMetrics).filter(UserMetrics.user_id == user_id).first()
        if metrics:
            metrics.avg_score = avg_score
            metrics.score_by_skill = score_by_skill
            metrics.total_interviews = total_interviews
        else:
            metrics = UserMetrics(
                user_id=user_id,
                avg_score=avg_score,
                score_by_skill=score_by_skill,
                total_interviews=total_interviews,
            )
            self.db.add(metrics)

        self.db.commit()
        self.db.refresh(metrics)
        return metrics

    def analyze_weak_areas(
        self,
        user_id: int,
        threshold: float = 60.0,
    ) -> list[dict]:
        """
        Identifica skills con score promedio bajo el umbral configurable.
        Retorna lista de { skill, score, priority } ordenada por score ascendente.

        Priority:
          score < 40  → high
          40 <= score < 50 → medium
          50 <= score < threshold → low
        """
        by_category = self.score_by_category(user_id)
        weak = []

        for skill, avg_score in by_category.items():
            if avg_score < threshold:
                if avg_score < 40:
                    priority = "high"
                elif avg_score < 50:
                    priority = "medium"
                else:
                    priority = "low"

                weak.append({
                    "skill": skill,
                    "score": avg_score,
                    "priority": priority,
                })

        return sorted(weak, key=lambda x: x["score"])
