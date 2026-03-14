from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from models.job_role import JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from schemas.role import RoleResponseSchema
from services.role_service import RoleService


router = APIRouter(
    prefix="/roles",
    tags=["Roles"],
)


@router.get("")
def list_roles(
    response: Response,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    name: str | None = Query(default=None),
    category: JobRoleCategory | None = Query(default=None),
    seniority_level: SeniorityLevel | None = Query(default=None),
    min_english_level: RoleEnglishLevel | None = Query(default=None),
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = RoleService(db)
    result = service.list_roles(
        page=page,
        size=size,
        name=name,
        category=category,
        seniority_level=seniority_level,
        min_english_level=min_english_level,
        active=active,
    )

    response.status_code = status.HTTP_200_OK
    return {
        "items": [
            RoleResponseSchema.model_validate(role).model_dump(mode="json")
            for role in result["items"]
        ],
        "page": result["page"],
        "size": result["size"],
        "total": result["total"],
    }
