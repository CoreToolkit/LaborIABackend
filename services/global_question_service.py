import hashlib

from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm import Session

from ai.question_deduplication import normalize_question
from repositories.global_question_repository import GlobalQuestionRepository


class GlobalQuestionService:
    def __init__(self, db: Session):
        self.repo = GlobalQuestionRepository(db)

    def list_all_questions_texts(self) -> list[str]:
        return self.repo.list_all_texts()

    def record_question(self, question_text: str) -> bool:
        normalized = normalize_question(question_text)
        if not normalized:
            return False

        question_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if self.repo.get_by_hash(question_hash):
            return False

        try:
            self.repo.create(
                question_text=question_text,
                normalized_text=normalized,
                question_hash=question_hash,
            )
            return True
        except IntegrityError:
            self.repo.db.rollback()
            return False
