from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from services.badge_service import BadgeService

router = APIRouter(
    prefix="/badges",
    tags=["Badges"],
)


class BadgeProgressResponse(BaseModel):
    id: int
    name: str
    description: str | None
    icon: str | None
    condition_type: str | None
    condition_value: str | None
    is_unlocked: bool
    progress: float


@router.get("/me", response_model=list[BadgeProgressResponse])
def get_my_badges(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Returns all badges with unlock status and progress toward each condition (0.0–1.0).
    Locked badges include progress so the frontend can render progress bars.
    """
    user_id: int = current_user["id"]
    service = BadgeService(db)
    return service.get_user_badges_with_progress(user_id)
