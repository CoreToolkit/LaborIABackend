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
    total_interviews: int
    last_updated: str | None


class TimelinePointResponse(BaseModel):
    period: str
    avg_score: float
    count: int


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
        total_interviews=metrics.total_interviews,
        last_updated=str(metrics.last_updated) if metrics.last_updated else None,
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
