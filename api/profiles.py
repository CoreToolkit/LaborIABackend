from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from exceptions.profile_exceptions import (
    ExperienceNotFoundError,
    ExperienceValidationError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileValidationError,
    SkillNotFoundError,
)
from schemas.experience import ExperienceCreate, ExperienceResponse, ExperienceUpdate
from schemas.skill import SkillCreate, SkillResponse, SkillUpdate
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


@router.post("/me/experiences")
def create_my_experience(
    experience_data: ExperienceCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        experience = service.create_experience(user_id, experience_data)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ExperienceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc

    response.status_code = status.HTTP_201_CREATED
    return ExperienceResponse.model_validate(experience).model_dump(mode="json")


@router.get("/me/experiences")
def list_my_experiences(
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        experiences = service.list_experiences(user_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    response.status_code = status.HTTP_200_OK
    return [ExperienceResponse.model_validate(experience).model_dump(mode="json") for experience in experiences]


@router.put("/me/experiences/{experience_id}")
def update_my_experience(
    experience_id: int,
    experience_data: ExperienceUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        experience = service.update_experience(user_id, experience_id, experience_data)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ExperienceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ExperienceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc

    response.status_code = status.HTTP_200_OK
    return ExperienceResponse.model_validate(experience).model_dump(mode="json")


@router.delete("/me/experiences/{experience_id}")
def delete_my_experience(
    experience_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        service.delete_experience(user_id, experience_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ExperienceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/skills")
def create_my_skill(
    skill_data: SkillCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        skill = service.create_skill(user_id, skill_data)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    response.status_code = status.HTTP_201_CREATED
    return SkillResponse.model_validate(skill).model_dump(mode="json")


@router.get("/me/skills")
def list_my_skills(
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        skills = service.list_skills(user_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    response.status_code = status.HTTP_200_OK
    return [SkillResponse.model_validate(skill).model_dump(mode="json") for skill in skills]


@router.put("/me/skills/{skill_id}")
def update_my_skill(
    skill_id: int,
    skill_data: SkillUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        skill = service.update_skill(user_id, skill_id, skill_data)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    response.status_code = status.HTTP_200_OK
    return SkillResponse.model_validate(skill).model_dump(mode="json")


@router.delete("/me/skills/{skill_id}")
def delete_my_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = ProfileService(db)
    user_id = current_user["id"]

    try:
        service.delete_skill(user_id, skill_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


