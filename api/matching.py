from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from services.matching_service import MatchingService


router = APIRouter(
    prefix="/matching",
    tags=["Matching"],
)


@router.post("/calculate")
def calculate_matching(
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = MatchingService(db)
    result = service.calculate_and_cache_matches_for_user(current_user["id"])

    response.status_code = status.HTTP_200_OK
    return result
