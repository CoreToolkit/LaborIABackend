from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from exceptions.role_exceptions import RoleNotFoundError
from repositories.profile_repository import ProfileRepository
from repositories.role_repository import RoleRepository
from utils.string_normalization import normalize_skill_name


class MatchingService:
    def __init__(self, db: Session):
        self.profile_repo = ProfileRepository(db)
        self.role_repo = RoleRepository(db)

    def calculate_skill_match(self, user_id: int, role_id: UUID) -> float:
        profile = self.profile_repo.get_by_user_id(user_id)
        if not profile:
            return 0.0

        skills = self.profile_repo.list_skills_by_profile_id(profile.id)
        if not skills:
            return 0.0

        role = self.role_repo.get_role_by_id(role_id)
        if not role:
            raise RoleNotFoundError()
        if not role.role_skills:
            return 0.0

        normalized_user_skills: set[str] = set()
        for skill in skills:
            normalized_skill = normalize_skill_name(skill.name)
            if normalized_skill:
                normalized_user_skills.add(normalized_skill)
        if not normalized_user_skills:
            return 0.0

        total_weight = sum(role_skill.importance_weight for role_skill in role.role_skills)
        if total_weight <= 0:
            return 0.0

        matched_weight = 0
        matched_technologies: set[str] = set()

        for role_skill in role.role_skills:
            technology = role_skill.technology
            if not technology:
                continue

            normalized_technology = normalize_skill_name(technology.name)
            if not normalized_technology:
                continue
            if normalized_technology in matched_technologies:
                continue
            if normalized_technology not in normalized_user_skills:
                continue

            matched_weight += role_skill.importance_weight
            matched_technologies.add(normalized_technology)

        percentage = (matched_weight / total_weight) * 100
        return round(min(max(percentage, 0.0), 100.0), 2)
