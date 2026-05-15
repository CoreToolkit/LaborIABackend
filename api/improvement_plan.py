from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from services.improvement_plan_service import ImprovementPlanService

router = APIRouter(
    prefix="/improvement-plan",
    tags=["Improvement Plan"],
)


class ResourceItem(BaseModel):
    title: str
    url: str
    type: str


class PlanItemResponse(BaseModel):
    id: int
    skill: str
    priority: str
    current_score: float | None
    target_score: float
    status: str
    resources: list[ResourceItem]
    ai_feedback: str | None
    completed_at: str | None


class ImprovementPlanResponse(BaseModel):
    id: int
    version: int
    last_updated_at: str | None
    items: list[PlanItemResponse]


class HistoryEntryResponse(BaseModel):
    id: int
    version: int
    trigger: str
    snapshot: dict
    created_at: str


class RefreshResponse(BaseModel):
    updated: bool
    reason: str
    plan: ImprovementPlanResponse


def _serialize_item(item) -> PlanItemResponse:
    return PlanItemResponse(
        id=item.id,
        skill=item.skill,
        priority=item.priority,
        current_score=item.current_score,
        target_score=item.target_score,
        status=item.status,
        resources=[ResourceItem(**r) for r in (item.resources or [])],
        ai_feedback=item.ai_feedback,
        completed_at=str(item.completed_at) if item.completed_at else None,
    )


def _serialize_plan(plan) -> ImprovementPlanResponse:
    return ImprovementPlanResponse(
        id=plan.id,
        version=plan.version,
        last_updated_at=str(plan.last_updated_at) if plan.last_updated_at else None,
        items=[_serialize_item(i) for i in sorted(plan.items, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.priority, 3))],
    )


@router.get("/me", response_model=ImprovementPlanResponse)
def get_my_plan(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Returns the active improvement plan for the authenticated user.
    Creates the initial plan if none exists yet.
    """
    user_id: int = current_user["id"]
    service = ImprovementPlanService(db)
    plan = service.get_or_create_plan(user_id)
    return _serialize_plan(plan)


@router.post("/refresh", response_model=RefreshResponse)
def refresh_plan(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Scans for changes (completed skills, new evaluations, weekly schedule).
    Only calls AI and updates the plan if changes are detected.
    Returns whether the plan was updated and the reason.
    """
    user_id: int = current_user["id"]
    service = ImprovementPlanService(db)
    result = service.refresh(user_id, trigger="manual")
    return RefreshResponse(
        updated=result["updated"],
        reason=result["reason"],
        plan=_serialize_plan(result["plan"]),
    )


@router.get("/history", response_model=list[HistoryEntryResponse])
def get_plan_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Returns all historical versions of the improvement plan, newest first.
    Each entry contains a full snapshot of the plan at that point in time.
    """
    user_id: int = current_user["id"]
    service = ImprovementPlanService(db)
    history = service.get_history(user_id)
    return [
        HistoryEntryResponse(
            id=h.id,
            version=h.version,
            trigger=h.trigger,
            snapshot=h.snapshot,
            created_at=str(h.created_at),
        )
        for h in history
    ]
