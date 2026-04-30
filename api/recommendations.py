# api/recommendations.py
# ─────────────────────────────────────────────────────────────────────────────
# TASK-027-05: GET /recommendations
# Retorna recomendaciones de roles personalizadas con skill_gaps, priority
# y reason generado por LLM (con fallback si Azure falla).
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from services.recommendation_service import RecommendationService

router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"],
)


class SkillGapItem(BaseModel):
    name: str
    importance_weight: int
    is_required: bool


class RecommendationItem(BaseModel):
    role_id: str
    role_name: str
    match_score: float
    skill_gaps: list[SkillGapItem]
    priority: str
    reason: str


class RecommendationsResponse(BaseModel):
    items: list[RecommendationItem]
    total: int


@router.get("", response_model=RecommendationsResponse)
async def get_recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna recomendaciones de roles personalizadas para el usuario autenticado.
    Ordenadas por match_score descendente.
    Incluye skill_gaps, priority (high/medium/low) y reason generado por LLM.
    Si Azure falla, reason usa texto genérico — nunca bloquea la respuesta.
    """
    service = RecommendationService(db)
    items = await service.get_recommendations(user_id=current_user["id"], limit=limit)

    return RecommendationsResponse(
        items=[RecommendationItem(**item) for item in items],
        total=len(items),
    )
