from sqlalchemy import func
from sqlalchemy.orm import Session

from models.role_skill import RoleSkill
from models.technology import Technology


class TechnologyRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_technologies(
        self,
        *,
        page: int,
        size: int,
        name: str | None = None,
    ) -> tuple[list[Technology], int]:
        query = self.db.query(Technology)
        if name:
            query = query.filter(func.lower(Technology.name).like(f"%{name.lower()}%"))

        total = query.count()
        offset = (page - 1) * size
        items = query.order_by(Technology.name.asc()).offset(offset).limit(size).all()
        return items, total

    def get_by_id(self, technology_id: int) -> Technology | None:
        return self.db.query(Technology).filter(Technology.id == technology_id).first()

    def get_by_name(self, name: str) -> Technology | None:
        return self.db.query(Technology).filter(func.lower(Technology.name) == name.lower()).first()

    def create(self, technology_data: dict) -> Technology:
        technology = Technology(**technology_data)
        self.db.add(technology)
        self.db.commit()
        self.db.refresh(technology)
        return technology

    def update(self, technology: Technology, update_data: dict) -> Technology:
        for key, value in update_data.items():
            setattr(technology, key, value)
        self.db.commit()
        self.db.refresh(technology)
        return technology

    def delete(self, technology: Technology) -> None:
        self.db.delete(technology)
        self.db.commit()

    def is_in_use(self, technology_id: int) -> bool:
        return self.db.query(RoleSkill).filter(RoleSkill.technology_id == technology_id).first() is not None
