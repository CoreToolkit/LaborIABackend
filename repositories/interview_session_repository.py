from sqlalchemy.orm import Session

from models.interview_session import InterviewSession


class InterviewSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id_and_user_id(self, session_id: int, user_id: int) -> InterviewSession | None:
        return (
            self.db.query(InterviewSession)
            .filter(InterviewSession.id == session_id, InterviewSession.user_id == user_id)
            .first()
        )
