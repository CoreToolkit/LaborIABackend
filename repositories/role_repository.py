from sqlalchemy import func
from sqlalchemy.orm import Session

from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel


class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def _apply_filters(
        self,
        query,
        *,
        name: str | None = None,
        category: JobRoleCategory | None = None,
        seniority_level: SeniorityLevel | None = None,
        min_english_level: RoleEnglishLevel | None = None,
        active: bool | None = None,
    ):
        if name:
            query = query.filter(func.lower(JobRole.name).like(f"%{name.lower()}%"))
        if category is not None:
            query = query.filter(JobRole.category == category)
        if seniority_level is not None:
            query = query.filter(JobRole.seniority_level == seniority_level)
        if min_english_level is not None:
            query = query.filter(JobRole.min_english_level == min_english_level)
        if active is not None:
            query = query.filter(JobRole.active == active)
        return query

    def list_roles(
        self,
        *,
        page: int,
        size: int,
        name: str | None = None,
        category: JobRoleCategory | None = None,
        seniority_level: SeniorityLevel | None = None,
        min_english_level: RoleEnglishLevel | None = None,
        active: bool | None = None,
    ) -> tuple[list[JobRole], int]:
        query = self.db.query(JobRole)
        query = self._apply_filters(
            query,
            name=name,
            category=category,
            seniority_level=seniority_level,
            min_english_level=min_english_level,
            active=active,
        )

        total = query.count()
        offset = (page - 1) * size
        items = query.order_by(JobRole.name.asc()).offset(offset).limit(size).all()
        return items, total
