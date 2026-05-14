from sqlalchemy.orm import Session, selectinload

from models.interview_session import InterviewSession


class InterviewSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int) -> InterviewSession:
        session = InterviewSession(user_id=user_id)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def create_for_group(self, user_id: int, group_interview_session_id: int) -> InterviewSession:
        session = InterviewSession(
            user_id=user_id,
            group_interview_session_id=group_interview_session_id,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_by_user_id(
        self,
        user_id: int,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[InterviewSession]:
        query = (
            self.db.query(InterviewSession)
            .filter(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
        )
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def count_by_user_id(self, user_id: int) -> int:
        return (
            self.db.query(InterviewSession)
            .filter(InterviewSession.user_id == user_id)
            .count()
        )

    def get_by_id_and_user_id(self, session_id: int, user_id: int) -> InterviewSession | None:
        return (
            self.db.query(InterviewSession)
            .options(
                selectinload(InterviewSession.questions),
                selectinload(InterviewSession.evaluations),
            )
            .filter(InterviewSession.id == session_id, InterviewSession.user_id == user_id)
            .first()
        )

    def get_by_user_id_and_group_session_id(
        self,
        user_id: int,
        group_interview_session_id: int,
    ) -> InterviewSession | None:
        return (
            self.db.query(InterviewSession)
            .filter(
                InterviewSession.user_id == user_id,
                InterviewSession.group_interview_session_id == group_interview_session_id,
            )
            .order_by(InterviewSession.id.desc())
            .first()
        )
