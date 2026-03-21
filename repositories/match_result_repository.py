from sqlalchemy.orm import Session

from models.match_result import MatchResult


class MatchResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user_id(self, user_id: int) -> list[MatchResult]:
        return self.db.query(MatchResult).filter(MatchResult.user_id == user_id).all()

    def get_by_user_id_and_role_id(self, user_id: int, role_id) -> MatchResult | None:
        return (
            self.db.query(MatchResult)
            .filter(MatchResult.user_id == user_id, MatchResult.role_id == role_id)
            .first()
        )
