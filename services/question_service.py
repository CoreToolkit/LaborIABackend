from sqlalchemy.orm import Session

from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from repositories.interview_session_repository import InterviewSessionRepository
from repositories.question_repository import QuestionRepository
from schemas.question import QuestionCreateSchema


class QuestionService:
    def __init__(self, db: Session):
        self.question_repo = QuestionRepository(db)
        self.session_repo = InterviewSessionRepository(db)

    def create_question(self, question_data: QuestionCreateSchema, user_id: int):
        session = self.session_repo.get_by_id_and_user_id(question_data.interview_session_id, user_id)
        if not session:
            raise InterviewSessionNotFoundError()

        return self.question_repo.create(question_data.model_dump())

    def list_questions_by_session(self, interview_session_id: int, user_id: int):
        session = self.session_repo.get_by_id_and_user_id(interview_session_id, user_id)
        if not session:
            raise InterviewSessionNotFoundError()

        return self.question_repo.list_by_session_id(interview_session_id)
