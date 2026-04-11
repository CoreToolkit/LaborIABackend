from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from models.evaluation import Evaluation
from models.interview_session import InterviewSession
from schemas.question import QuestionCreateSchema, QuestionResponseSchema
from services.interview_flow import (
    EVENT_NEXT_QUESTION,
    EVENT_QUESTION_CREATED,
    EVALUATION_COMPLETED,
    EVALUATION_FAILED,
    EVALUATION_PENDING,
    QUESTION_CREATED,
    SESSION_CREATED,
    can_enter_question_created,
    resolve_next_state,
    state_from_evaluation_status,
)
from services.question_service import QuestionService


router = APIRouter(
    prefix="/questions",
    tags=["Questions"],
)


@router.post("")
def create_question(
    question_data: QuestionCreateSchema,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not can_enter_question_created(interview_session_id=question_data.interview_session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="interview_session_id invalido para crear pregunta",
        )

    session = (
        db.query(InterviewSession.id)
        .filter(
            InterviewSession.id == question_data.interview_session_id,
            InterviewSession.user_id == current_user["id"],
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=InterviewSessionNotFoundError().message,
        )

    latest_evaluation = (
        db.query(Evaluation.status)
        .filter(Evaluation.interview_session_id == question_data.interview_session_id)
        .order_by(Evaluation.evaluated_at.desc(), Evaluation.id.desc())
        .first()
    )
    latest_evaluation_status = latest_evaluation[0] if latest_evaluation else None

    flow_source_state = state_from_evaluation_status(latest_evaluation_status) or SESSION_CREATED
    flow_event = EVENT_QUESTION_CREATED
    if flow_source_state == EVALUATION_COMPLETED:
        flow_event = EVENT_NEXT_QUESTION

    flow_target_state = resolve_next_state(
        flow_source_state,
        event=flow_event,
        session_id=question_data.interview_session_id,
    )
    if flow_target_state != QUESTION_CREATED:
        status_value = (
            latest_evaluation_status.value
            if hasattr(latest_evaluation_status, "value")
            else latest_evaluation_status
        )
        if flow_source_state in {EVALUATION_PENDING, EVALUATION_FAILED}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede crear una nueva pregunta cuando la evaluacion actual esta en estado '{status_value}'",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Interview flow transition is not allowed for question_created",
        )

    service = QuestionService(db)

    try:
        question = service.create_question(question_data, current_user["id"])
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    response.status_code = status.HTTP_201_CREATED
    return QuestionResponseSchema.model_validate(question).model_dump(mode="json")
