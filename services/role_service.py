from sqlalchemy.orm import Session

from models.job_role import JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from repositories.role_repository import RoleRepository


class RoleService:
    def __init__(self, db: Session):
        self.repo = RoleRepository(db)

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
    ) -> dict:
        items, total = self.repo.list_roles(
            page=page,
            size=size,
            name=name,
            category=category,
            seniority_level=seniority_level,
            min_english_level=min_english_level,
            active=active,
        )
        return {
            "items": items,
            "page": page,
            "size": size,
            "total": total,
        }
