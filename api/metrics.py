# api/metrics.py
# ─────────────────────────────────────────────────────────────────────────────
# Router para métricas de rendimiento del usuario autenticado.
# TASK-026-06: GET /metrics/user
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from services.metrics_service import UserMetricsService

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
)


class UserMetricsResponse(BaseModel):
    avg_score: float
    score_by_skill: dict
    score_by_category: dict
    total_interviews: int
    last_updated: str | None


class TimelinePointResponse(BaseModel):
    period: str
    avg_score: float
    count: int


class EmployabilityBreakdown(BaseModel):
    interview_score: float
    profile_completeness: float
    avg_match_score: float


class EmployabilityScoreResponse(BaseModel):
    score: float
    breakdown: EmployabilityBreakdown
    last_updated: str | None
    motivational_message: str | None = None


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

    metrics = service.update_for_user(user_id)

    return UserMetricsResponse(
        avg_score=float(metrics.avg_score) if metrics.avg_score is not None else 0.0,
        score_by_skill=metrics.score_by_skill or {},
        score_by_category=metrics.score_by_category or {},
        total_interviews=metrics.total_interviews,
        last_updated=str(metrics.last_updated) if metrics.last_updated else None,
    )


@router.get("/employability", response_model=EmployabilityScoreResponse)
def get_employability_score(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna el puntaje global de empleabilidad del usuario autenticado.

    score = interview_score(60%) + profile_completeness(20%) + avg_match_score(20%)

    Incluye breakdown por componente y un mensaje motivacional cuando el usuario
    no ha completado ninguna entrevista aún.
    """
    user_id: int = current_user["id"]
    service = UserMetricsService(db)

    result = service.calculate_employability_score(user_id)
    metrics = service.update_for_user(user_id)

    motivational_message = None
    if result["total_interviews"] == 0:
        motivational_message = (
            "¡Completa tu primera entrevista para mejorar tu puntaje de empleabilidad!"
        )

    return EmployabilityScoreResponse(
        score=result["score"],
        breakdown=EmployabilityBreakdown(**result["breakdown"]),
        last_updated=str(metrics.last_updated) if metrics.last_updated else None,
        motivational_message=motivational_message,
    )


@router.get("/timeline", response_model=list[TimelinePointResponse])
def get_metrics_timeline(
    granularity: Literal["week", "month"] = Query(default="week"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna la evolución temporal del score del usuario.
    granularity:
      - week: agrupación por semana
      - month: agrupación por mes
    """
    user_id: int = current_user["id"]
    service = UserMetricsService(db)
    timeline = service.get_score_timeline(user_id=user_id, granularity=granularity)

    return [TimelinePointResponse(**item) for item in timeline]
