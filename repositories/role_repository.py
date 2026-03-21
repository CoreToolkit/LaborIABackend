from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.role_skill import RoleSkill
from models.technology import Technology


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

    def get_role_by_id(self, role_id) -> JobRole | None:
        return (
            self.db.query(JobRole)
            .options(
                selectinload(JobRole.role_skills).selectinload(RoleSkill.technology),
            )
            .filter(JobRole.id == role_id)
            .first()
        )

    def list_available_roles(self) -> list[JobRole]:
        return (
            self.db.query(JobRole)
            .options(
                selectinload(JobRole.role_skills).selectinload(RoleSkill.technology),
            )
            .filter(JobRole.active.is_(True))
            .order_by(JobRole.name.asc())
            .all()
        )

    def get_technologies_by_ids(self, technology_ids: list[int]) -> list[Technology]:
        if not technology_ids:
            return []
        return self.db.query(Technology).filter(Technology.id.in_(technology_ids)).all()

    def create_role(self, role_data: dict, role_skills_data: list[dict]) -> JobRole:
        role = JobRole(**role_data)
        self.db.add(role)
        self.db.flush()

        for role_skill_data in role_skills_data:
            self.db.add(RoleSkill(role_id=role.id, **role_skill_data))

        self.db.commit()
        return self.get_role_by_id(role.id)
