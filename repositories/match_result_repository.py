from sqlalchemy.orm import Session, joinedload

from models.job_role import JobRole
from models.match_result import MatchResult


class MatchResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user_id(self, user_id: int) -> list[MatchResult]:
        return self.db.query(MatchResult).filter(MatchResult.user_id == user_id).all()

    def list_top_recommendations_by_user_id(self, user_id: int, limit: int = 10) -> list[MatchResult]:
        return (
            self.db.query(MatchResult)
            .join(MatchResult.job_role)
            .options(joinedload(MatchResult.job_role))
            .filter(MatchResult.user_id == user_id, JobRole.active.is_(True))
            .order_by(MatchResult.total_score.desc(), MatchResult.id.asc())
            .limit(limit)
            .all()
        )

    def get_by_user_id_and_role_id(self, user_id: int, role_id) -> MatchResult | None:
        return (
            self.db.query(MatchResult)
            .filter(MatchResult.user_id == user_id, MatchResult.role_id == role_id)
            .first()
        )
