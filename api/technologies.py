from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from exceptions.technology_exceptions import (
    TechnologyAuthorizationError,
    TechnologyInUseError,
    TechnologyNotFoundError,
    TechnologyValidationError,
)
from schemas.technology import TechnologyCreate, TechnologyResponse, TechnologyUpdate
from services.technology_service import TechnologyService


router = APIRouter(
    prefix="/technologies",
    tags=["Technologies"],
)


@router.get("")
def list_technologies(
    response: Response,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    name: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = TechnologyService(db)
    result = service.list_technologies(page=page, size=size, name=name)

    response.status_code = status.HTTP_200_OK
    return {
        "items": [
            TechnologyResponse.model_validate(technology).model_dump(mode="json")
            for technology in result["items"]
        ],
        "page": result["page"],
        "size": result["size"],
        "total": result["total"],
    }


@router.get("/{technology_id}")
def get_technology_detail(
    technology_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = TechnologyService(db)

    try:
        technology = service.get_technology_detail(technology_id)
    except TechnologyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    response.status_code = status.HTTP_200_OK
    return TechnologyResponse.model_validate(technology).model_dump(mode="json")


@router.post("")
def create_technology(
    technology_data: TechnologyCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = TechnologyService(db)

    try:
        technology = service.create_technology(technology_data, current_user)
    except TechnologyAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc
    except TechnologyValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc

    response.status_code = status.HTTP_201_CREATED
    return TechnologyResponse.model_validate(technology).model_dump(mode="json")


@router.put("/{technology_id}")
def update_technology(
    technology_id: int,
    technology_data: TechnologyUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = TechnologyService(db)

    try:
        technology = service.update_technology(technology_id, technology_data, current_user)
    except TechnologyAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc
    except TechnologyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except TechnologyValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc

    response.status_code = status.HTTP_200_OK
    return TechnologyResponse.model_validate(technology).model_dump(mode="json")


@router.delete("/{technology_id}")
def delete_technology(
    technology_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = TechnologyService(db)

    try:
        service.delete_technology(technology_id, current_user)
    except TechnologyAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc
    except TechnologyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except TechnologyInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
