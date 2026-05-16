from sqlalchemy.orm import Session

from exceptions.technology_exceptions import (
    TechnologyAuthorizationError,
    TechnologyInUseError,
    TechnologyNotFoundError,
    TechnologyValidationError,
)
from core.config import settings
from repositories.technology_repository import TechnologyRepository
from schemas.technology import TechnologyCreate, TechnologyUpdate


class TechnologyService:
    def __init__(self, db: Session):
        self.repo = TechnologyRepository(db)

    @staticmethod
    def _get_admin_emails() -> set[str]:
        raw = settings.ADMIN_EMAILS
        return {email.strip().lower() for email in raw.split(",") if email.strip()}

    @classmethod
    def _ensure_admin(cls, current_user: dict) -> None:
        email = (current_user.get("email") or "").strip().lower()
        if not email or email not in cls._get_admin_emails():
            raise TechnologyAuthorizationError()

    def list_technologies(
        self,
        *,
        page: int,
        size: int,
        name: str | None = None,
    ) -> dict:
        items, total = self.repo.list_technologies(page=page, size=size, name=name)
        return {
            "items": items,
            "page": page,
            "size": size,
            "total": total,
        }

    def get_technology_detail(self, technology_id: int):
        technology = self.repo.get_by_id(technology_id)
        if not technology:
            raise TechnologyNotFoundError()
        return technology

    def create_technology(self, technology_data: TechnologyCreate, current_user: dict):
        self._ensure_admin(current_user)

        existing = self.repo.get_by_name(technology_data.name)
        if existing:
            raise TechnologyValidationError("Technology name already exists")

        return self.repo.create(technology_data.model_dump())

    def update_technology(
        self,
        technology_id: int,
        technology_data: TechnologyUpdate,
        current_user: dict,
    ):
        self._ensure_admin(current_user)

        technology = self.repo.get_by_id(technology_id)
        if not technology:
            raise TechnologyNotFoundError()

        existing = self.repo.get_by_name(technology_data.name)
        if existing and existing.id != technology_id:
            raise TechnologyValidationError("Technology name already exists")

        return self.repo.update(technology, technology_data.model_dump())

    def delete_technology(self, technology_id: int, current_user: dict) -> None:
        self._ensure_admin(current_user)

        technology = self.repo.get_by_id(technology_id)
        if not technology:
            raise TechnologyNotFoundError()
        if self.repo.is_in_use(technology_id):
            raise TechnologyInUseError()

        self.repo.delete(technology)
