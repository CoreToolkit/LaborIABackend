from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from schemas.role import RoleResponseSchema
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


@router.get("/recommendations")
def get_matching_recommendations(
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = MatchingService(db)
    cached_recommendations = service.get_cached_recommendations_for_user(current_user["id"], limit=10)
    recommendations: list[dict[str, object]] = []

    for match_result in cached_recommendations:
        role = match_result.job_role
        if role is None:
            continue

        role_payload = RoleResponseSchema.model_validate(role).model_dump(mode="json")
        recommendations.append(
            {
                "role_id": role_payload["id"],
                "role_name": role_payload["name"],
                "total_score": float(match_result.total_score),
                "category": role_payload["category"],
                "seniority_level": role_payload["seniority_level"],
                "min_english_level": role_payload["min_english_level"],
                "estimated_salary_min_cop": role_payload["estimated_salary_min_cop"],
                "estimated_salary_max_cop": role_payload["estimated_salary_max_cop"],
                "active": role_payload["active"],
            }
        )

    response.status_code = status.HTTP_200_OK
    return {
        "recommendations": recommendations,
        "total": len(recommendations),
    }
