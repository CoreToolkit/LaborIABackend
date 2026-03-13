from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from exceptions.profile_exceptions import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileValidationError,
)
from services.profile_service import ProfileService



router = APIRouter(
    prefix="/profiles", 
    tags=["Profiles"]
    )


def _serialize_profile(profile):
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "full_name": profile.full_name,
        "career": profile.career,
        "university": profile.university,
        "graduation_date": str(profile.graduation_date) if profile.graduation_date else None,
        "description": profile.description,
        "english_level": profile.english_level.value if profile.english_level else None,
        "preferred_location": profile.preferred_location,
        "preferred_employment_type": profile.preferred_employment_type.value if profile.preferred_employment_type else None,
        "salary_expectation": float(profile.salary_expectation) if profile.salary_expectation else None,
    }


@router.post("")
def create_profile(
    profile_data: dict,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        profile = service.create_profile(user_id, profile_data)
    except ProfileAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except ProfileValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc

    response.status_code = status.HTTP_201_CREATED
    return _serialize_profile(profile)


@router.get("/me")
def get_my_profile(
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    profile = service.get_profile_by_user_id(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ProfileNotFoundError.default_message)

    response.status_code = status.HTTP_200_OK
    return _serialize_profile(profile)


@router.put("/me")
def update_my_profile(
    profile_data: dict,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        profile = service.update_profile(user_id, profile_data)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ProfileValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc

    response.status_code = status.HTTP_200_OK
    return _serialize_profile(profile)


@router.delete("/me")
def delete_my_profile(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        service.delete_profile(user_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


