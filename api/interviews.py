import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from services.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interviews",
    tags=["Interviews"],
)


class EvaluationDetail(BaseModel):
    evaluation_id: str
    question_text: str | None
    category: str | None
    difficulty: str | None
    score: float | None
    feedback: str | None
    score_breakdown: dict
    topics_covered: list[str]
    topics_missing: list[str]


class SessionComparison(BaseModel):
    has_previous: bool
    previous_session_id: int | None
    previous_score: float | None
    improvement: float | None
    trend: str


class BadgeSummary(BaseModel):
    id: int
    name: str
    description: str | None
    icon: str | None


class SessionReportResponse(BaseModel):
    session_id: int
    session_score: float | None
    total_questions: int
    completed_questions: int
    evaluations: list[EvaluationDetail]
    comparison: SessionComparison
    badges_unlocked: list[BadgeSummary]
    session_created_at: str


class ReportSummaryResponse(BaseModel):
    session_id: int
    session_score: float | None
    session_created_at: str
    total_questions: int
    completed_questions: int
    trend: str
    improvement: float | None
    previous_score: float | None
    badges_count: int


@router.get("/{session_id}/report", response_model=SessionReportResponse)
def get_session_report(
    session_id: int,
    unlock_badges: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna el reporte completo de una sesión de entrevista:
    - Score de la sesión y detalle por pregunta
    - Comparación con la sesión anterior (mejora o retroceso)
    - Badges desbloqueados durante esta sesión

    Solo el dueño de la sesión puede ver su reporte.
    """
    start = time.monotonic()
    user_id: int = current_user["id"]
    report = ReportService(db).get_session_report(
        session_id=session_id,
        user_id=user_id,
        unlock_badges=unlock_badges,
    )

    if report is None:
        raise HTTPException(status_code=404, detail="Session not found or does not belong to you.")

    logger.info(
        "interviews.report duration_ms=%s user_id=%s session_id=%s unlock_badges=%s",
        round((time.monotonic() - start) * 1000, 1),
        user_id,
        session_id,
        unlock_badges,
    )
    return SessionReportResponse(**report)


@router.get("/reports", response_model=list[SessionReportResponse])
def list_session_reports(
    limit: int = Query(default=3, ge=1, le=20),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna el historial de reportes de entrevistas del usuario autenticado.
    Devuelve una lista ordenada del reporte más reciente al más antiguo.
    """
    start = time.monotonic()
    user_id: int = current_user["id"]
    reports = ReportService(db).list_session_reports(
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    logger.info(
        "interviews.reports duration_ms=%s user_id=%s limit=%s offset=%s count=%s",
        round((time.monotonic() - start) * 1000, 1),
        user_id,
        limit,
        offset,
        len(reports),
    )
    return [SessionReportResponse(**report) for report in reports]


@router.get("/reports/summary", response_model=list[ReportSummaryResponse])
def list_session_reports_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna un resumen ligero del historial de reportes para uso en dashboards/tarjetas.
    Sin evaluaciones detalladas ni efectos secundarios.
    """
    start = time.monotonic()
    user_id: int = current_user["id"]
    summaries = ReportService(db).list_session_reports_summary(user_id=user_id)

    logger.info(
        "interviews.reports_summary duration_ms=%s user_id=%s count=%s",
        round((time.monotonic() - start) * 1000, 1),
        user_id,
        len(summaries),
    )
    return [ReportSummaryResponse(**s) for s in summaries]
