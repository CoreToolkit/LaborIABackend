import os
from uuid import UUID

from exceptions.role_exceptions import RoleAuthorizationError, RoleNotFoundError, RoleValidationError
from sqlalchemy.orm import Session

from models.job_role import JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from repositories.role_repository import RoleRepository
from schemas.role import RoleCreateSchema


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

    def get_role_detail(self, role_id: UUID):
        role = self.repo.get_role_by_id(role_id)
        if not role:
            raise RoleNotFoundError()
        return role

    @staticmethod
    def _get_admin_emails() -> set[str]:
        raw = os.getenv("ADMIN_EMAILS", "")
        return {email.strip().lower() for email in raw.split(",") if email.strip()}

    @classmethod
    def _ensure_admin(cls, current_user: dict) -> None:
        email = (current_user.get("email") or "").strip().lower()
        if not email or email not in cls._get_admin_emails():
            raise RoleAuthorizationError()

    def create_role(self, role_data: RoleCreateSchema, current_user: dict):
        self._ensure_admin(current_user)

        technology_ids = [role_skill.technology_id for role_skill in role_data.role_skills]
        if len(technology_ids) != len(set(technology_ids)):
            raise RoleValidationError("role_skills contains duplicate technology_id")

        existing_technologies = self.repo.get_technologies_by_ids(technology_ids)
        existing_ids = {technology.id for technology in existing_technologies}
        missing_ids = [technology_id for technology_id in technology_ids if technology_id not in existing_ids]
        if missing_ids:
            raise RoleValidationError("One or more technologies do not exist")

        role_payload = role_data.model_dump(exclude={"role_skills"})
        role_skills_payload = [role_skill.model_dump() for role_skill in role_data.role_skills]
        return self.repo.create_role(role_payload, role_skills_payload)
