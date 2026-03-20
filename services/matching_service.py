from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from models.job_role import SeniorityLevel
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

    def _get_profile(self, user_id: int):
        return self.profile_repo.get_by_user_id(user_id)

    def _get_normalized_user_skills(self, user_id: int) -> set[str]:
        profile = self._get_profile(user_id)
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

    def _get_user_experiences(self, user_id: int):
        profile = self._get_profile(user_id)
        if not profile:
            return []
        return self.profile_repo.list_experiences_by_profile_id(profile.id)

    @staticmethod
    def _get_required_experience_months(role) -> int:
        minimum_by_seniority = {
            SeniorityLevel.JUNIOR: 12,
            SeniorityLevel.MID: 24,
            SeniorityLevel.SENIOR: 48,
        }
        return minimum_by_seniority.get(role.seniority_level, 24)

    @staticmethod
    def _calculate_experience_months(start_date: date, end_date: date) -> int:
        if end_date <= start_date:
            return 0

        months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        if end_date.day < start_date.day:
            months -= 1

        return max(months, 0)

    @classmethod
    def _get_total_experience_months(cls, experiences, reference_date: date | None = None) -> int:
        if not experiences:
            return 0

        reference_date = reference_date or date.today()
        total_months = 0

        for experience in experiences:
            start_date = experience.start_date
            if not start_date:
                continue

            if experience.currently_working:
                effective_end_date = reference_date
            elif experience.end_date is not None:
                effective_end_date = experience.end_date
            else:
                effective_end_date = start_date

            total_months += cls._calculate_experience_months(start_date, effective_end_date)

        return total_months

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

    def calculate_experience_match(self, user_id: int, role_id: UUID) -> float:
        profile = self._get_profile(user_id)
        if not profile:
            return 0.0

        experiences = self._get_user_experiences(user_id)
        if not experiences:
            return 0.0

        role = self._get_role_or_raise(role_id)
        required_months = self._get_required_experience_months(role)
        if required_months <= 0:
            return 100.0

        user_months = self._get_total_experience_months(experiences)
        if user_months <= 0:
            return 0.0

        percentage = (user_months / required_months) * 100
        return round(min(max(percentage, 0.0), 100.0), 2)
