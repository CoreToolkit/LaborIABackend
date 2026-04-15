from sqlalchemy.orm import Session

from exceptions.interview_session_exceptions import InterviewSessionNotFoundError
from repositories.interview_session_repository import InterviewSessionRepository


class InterviewSessionService:
    def __init__(self, db: Session):
        self.repo = InterviewSessionRepository(db)

    def create_session(self, user_id: int):
        return self.repo.create(user_id)

    def list_sessions(self, user_id: int):
        return self.repo.list_by_user_id(user_id)

    def get_session_detail(self, user_id: int, session_id: int):
        session = self.repo.get_by_id_and_user_id(session_id, user_id)
        if not session:
            raise InterviewSessionNotFoundError()
        return session
