from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.jwt import get_current_user
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from schemas.question import QuestionCreateSchema, QuestionResponseSchema
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
    service = QuestionService(db)

    try:
        question = service.create_question(question_data, current_user["id"])
    except InterviewSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    response.status_code = status.HTTP_201_CREATED
    return QuestionResponseSchema.model_validate(question).model_dump(mode="json")
