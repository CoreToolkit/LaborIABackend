from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from exceptions.role_exceptions import RoleNotFoundError
from repositories.profile_repository import ProfileRepository
from repositories.role_repository import RoleRepository
from utils.string_normalization import normalize_skill_name


@dataclass(frozen=True)
class _RoleRequirement:
    name: str
    normalized_name: str
    importance_weight: int
    is_required: bool


class MatchingService:
    def __init__(self, db: Session):
        self.profile_repo = ProfileRepository(db)
        self.role_repo = RoleRepository(db)

    def _get_role_or_raise(self, role_id: UUID):
        role = self.role_repo.get_role_by_id(role_id)
        if not role:
            raise RoleNotFoundError()
        return role

    def _get_normalized_user_skills(self, user_id: int) -> set[str]:
        profile = self.profile_repo.get_by_user_id(user_id)
        if not profile:
            return set()

        skills = self.profile_repo.list_skills_by_profile_id(profile.id)
        if not skills:
            return set()

        normalized_user_skills: set[str] = set()
        for skill in skills:
            normalized_skill = normalize_skill_name(skill.name)
            if normalized_skill:
                normalized_user_skills.add(normalized_skill)
        return normalized_user_skills

    @staticmethod
    def _get_unique_role_requirements(role) -> list[_RoleRequirement]:
        if not role.role_skills:
            return []

        unique_requirements: list[_RoleRequirement] = []
        seen_technologies: set[str] = set()

        sorted_role_skills = sorted(
            role.role_skills,
            key=lambda role_skill: role_skill.importance_weight,
            reverse=True,
        )
        for role_skill in sorted_role_skills:
            technology = role_skill.technology
            if not technology:
                continue

            normalized_technology = normalize_skill_name(technology.name)
            if not normalized_technology or normalized_technology in seen_technologies:
                continue

            seen_technologies.add(normalized_technology)
            unique_requirements.append(
                _RoleRequirement(
                    name=technology.name.strip(),
                    normalized_name=normalized_technology,
                    importance_weight=role_skill.importance_weight,
                    is_required=role_skill.is_required,
                )
            )

        return unique_requirements

    def calculate_skill_match(self, user_id: int, role_id: UUID) -> float:
        normalized_user_skills = self._get_normalized_user_skills(user_id)
        if not normalized_user_skills:
            return 0.0

        role = self._get_role_or_raise(role_id)
        requirements = self._get_unique_role_requirements(role)
        if not requirements:
            return 0.0

        total_weight = sum(requirement.importance_weight for requirement in requirements)
        if total_weight <= 0:
            return 0.0

        matched_weight = 0
        for requirement in requirements:
            if requirement.normalized_name not in normalized_user_skills:
                continue

            matched_weight += requirement.importance_weight

        percentage = (matched_weight / total_weight) * 100
        return round(min(max(percentage, 0.0), 100.0), 2)

    def detect_skill_gaps(self, user_id: int, role_id: UUID) -> list[dict[str, object]]:
        role = self._get_role_or_raise(role_id)
        requirements = self._get_unique_role_requirements(role)
        if not requirements:
            return []

        normalized_user_skills = self._get_normalized_user_skills(user_id)

        gaps: list[dict[str, object]] = []
        for requirement in requirements:
            if requirement.normalized_name in normalized_user_skills:
                continue

            gaps.append(
                {
                    "name": requirement.name,
                    "importance_weight": requirement.importance_weight,
                    "is_required": requirement.is_required,
                }
            )

        return gaps
