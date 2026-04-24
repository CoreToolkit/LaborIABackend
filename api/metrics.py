# api/metrics.py
# ─────────────────────────────────────────────────────────────────────────────
# Router para métricas de rendimiento del usuario autenticado.
# TASK-026-06: GET /metrics/user
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from models.user_metrics import UserMetrics
from services.metrics_service import UserMetricsService

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
)


class UserMetricsResponse(BaseModel):
    avg_score: float
    score_by_skill: dict
    total_interviews: int
    last_updated: str | None


@router.get("/user", response_model=UserMetricsResponse)
def get_user_metrics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna métricas de rendimiento del usuario autenticado.
    Calcula y persiste avg_score, score_by_skill y total_interviews.
    Si no hay evaluaciones, retorna valores en cero.
    """
    user_id: int = current_user["id"]
    service = UserMetricsService(db)

    avg_score = service.calculate_average_score(user_id)
    score_by_skill = service.score_by_category(user_id)

    # Contar entrevistas únicas con evaluaciones completadas
    from models.evaluation import Evaluation, EvaluationStatus
    from models.interview_session import InterviewSession
    from sqlalchemy import func as sqlfunc

    total_interviews = (
        db.query(sqlfunc.count(sqlfunc.distinct(Evaluation.interview_session_id)))
        .join(InterviewSession, Evaluation.interview_session_id == InterviewSession.id)
        .filter(
            InterviewSession.user_id == user_id,
            Evaluation.status == EvaluationStatus.COMPLETED,
        )
        .scalar()
    ) or 0

    # Upsert en user_metrics
    metrics = db.query(UserMetrics).filter(UserMetrics.user_id == user_id).first()
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
        db.add(metrics)
    db.commit()
    db.refresh(metrics)

    return UserMetricsResponse(
        avg_score=float(metrics.avg_score) if metrics.avg_score is not None else 0.0,
        score_by_skill=metrics.score_by_skill or {},
        total_interviews=metrics.total_interviews,
        last_updated=str(metrics.last_updated) if metrics.last_updated else None,
    )
