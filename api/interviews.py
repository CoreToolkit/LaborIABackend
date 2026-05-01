from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from services.report_service import ReportService

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


@router.get("/{session_id}/report", response_model=SessionReportResponse)
def get_session_report(
    session_id: int,
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
    user_id: int = current_user["id"]
    report = ReportService(db).get_session_report(session_id=session_id, user_id=user_id)

    if report is None:
        raise HTTPException(status_code=404, detail="Session not found or does not belong to you.")

    return SessionReportResponse(**report)
