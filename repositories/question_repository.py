from sqlalchemy.orm import Session

from models.question import Question


class QuestionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, question_data: dict) -> Question:
        question = Question(**question_data)
        self.db.add(question)
        self.db.commit()
        self.db.refresh(question)
        return question

    def list_by_session_id(self, interview_session_id: int) -> list[Question]:
        return (
            self.db.query(Question)
            .filter(Question.interview_session_id == interview_session_id)
            .order_by(Question.id.asc())
            .all()
        )
