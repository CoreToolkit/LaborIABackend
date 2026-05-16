from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.dependencies import get_interview_session_service
from core.jwt import get_current_user
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from schemas.interview_session import InterviewSessionDetailResponse, InterviewSessionResponse
from services.interview_session_service import InterviewSessionService
from services.interview_flow import resolve_session_created_snapshot


router = APIRouter(
    prefix="/sessions",
    tags=["Interview Sessions"],
)


@router.get("")
def list_sessions(
    response: Response,
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_meta: bool = Query(default=False),
    service: InterviewSessionService = Depends(get_interview_session_service),
    current_user: dict = Depends(get_current_user),
):
    sessions = service.list_sessions(current_user["id"], limit=limit, offset=offset)

    response.status_code = status.HTTP_200_OK
    items = [InterviewSessionResponse.model_validate(session).model_dump(mode="json") for session in sessions]
    if not include_meta:
        return items

    return {
        "items": items,
        "total": service.count_sessions(current_user["id"]),
        "limit": limit,
        "offset": offset,
    }

@router.post("")
def create_session(
    response: Response,
    service: InterviewSessionService = Depends(get_interview_session_service),
    current_user: dict = Depends(get_current_user),
):
    new_session = service.create_session(current_user["id"])

    session_snapshot = resolve_session_created_snapshot(
        session_id=new_session.id,
        user_id=current_user["id"],
    )
    if session_snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Interview flow validation failed for session_created",
        )

    response.status_code = status.HTTP_201_CREATED
    return InterviewSessionResponse.model_validate(new_session).model_dump(mode="json")


@router.get("/{session_id}")
def get_session_detail(
    session_id: int,
    response: Response,
    service: InterviewSessionService = Depends(get_interview_session_service),
    current_user: dict = Depends(get_current_user),
):
    try:
        session = service.get_session_detail(current_user["id"], session_id)
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    response.status_code = status.HTTP_200_OK
    return InterviewSessionDetailResponse.model_validate(session).model_dump(mode="json")
