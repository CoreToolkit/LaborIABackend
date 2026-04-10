from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from schemas.interview_session import InterviewSessionDetailResponse, InterviewSessionResponse
from services.interview_session_service import InterviewSessionService


router = APIRouter(
    prefix="/sessions",
    tags=["Interview Sessions"],
)


@router.get("")
def list_sessions(
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = InterviewSessionService(db)
    sessions = service.list_sessions(current_user["id"])

    response.status_code = status.HTTP_200_OK
    return [InterviewSessionResponse.model_validate(session).model_dump(mode="json") for session in sessions]

@router.post("")
def create_session(
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):

    service = InterviewSessionService(db)
    new_session = service.create_session(current_user["id"])
    response.status_code = status.HTTP_201_CREATED
    return InterviewSessionResponse.model_validate(new_session).model_dump(mode="json")


@router.get("/{session_id}")
def get_session_detail(
    session_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    service = InterviewSessionService(db)

    try:
        session = service.get_session_detail(current_user["id"], session_id)
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    response.status_code = status.HTTP_200_OK
    return InterviewSessionDetailResponse.model_validate(session).model_dump(mode="json")
