from sqlalchemy.orm import Session

from models.global_question import GlobalQuestion


class GlobalQuestionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_hash(self, question_hash: str) -> GlobalQuestion | None:
        return (
            self.db.query(GlobalQuestion)
            .filter(GlobalQuestion.question_hash == question_hash)
            .first()
        )

    def list_all_texts(self) -> list[str]:
        rows = self.db.query(GlobalQuestion.question_text).order_by(GlobalQuestion.id.asc()).all()
        return [row[0] for row in rows if row and row[0]]

    def create(self, question_text: str, normalized_text: str, question_hash: str) -> GlobalQuestion:
        item = GlobalQuestion(
            question_text=question_text,
            normalized_text=normalized_text,
            question_hash=question_hash,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item
