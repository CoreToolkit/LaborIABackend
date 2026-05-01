from sqlalchemy.orm import Session, joinedload

from models.badge import Badge, UserBadge


class BadgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[Badge]:
        return self.db.query(Badge).all()

    def list_by_user(self, user_id: int) -> list[UserBadge]:
        return (
            self.db.query(UserBadge)
            .options(joinedload(UserBadge.badge))
            .filter(UserBadge.user_id == user_id)
            .all()
        )

    def list_by_user_since(self, user_id: int, since) -> list[UserBadge]:
        return (
            self.db.query(UserBadge)
            .options(joinedload(UserBadge.badge))
            .filter(
                UserBadge.user_id == user_id,
                UserBadge.unlocked_at >= since,
            )
            .all()
        )

    def unlock_badge(self, user_id: int, badge_id: int) -> UserBadge:
        user_badge = UserBadge(user_id=user_id, badge_id=badge_id)
        self.db.add(user_badge)
        self.db.flush()
        return user_badge
