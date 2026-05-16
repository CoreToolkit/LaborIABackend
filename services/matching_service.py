from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from exceptions.role_exceptions import RoleNotFoundError
from models.match_result import MatchResult
from repositories.match_result_repository import MatchResultRepository
from repositories.profile_repository import ProfileRepository
from repositories.role_repository import RoleRepository
from services.match_calculator import (
    calculate_education_match_for_role,
    calculate_experience_match_for_role,
    calculate_preferences_match_for_role,
    calculate_skill_match_for_role,
    calculate_weighted_match_score,
    detect_skill_gaps_for_role,
    normalize_decimal,
    normalize_skills,
)


class MatchingService:
    def __init__(self, db: Session):
        self.db = db
        self.match_result_repo = MatchResultRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.role_repo = RoleRepository(db)

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _get_role_or_raise(self, role_id: UUID):
        role = self.role_repo.get_role_by_id(role_id)
        if not role:
            raise RoleNotFoundError()
        return role

    def _get_profile(self, user_id: int):
        return self.profile_repo.get_by_user_id(user_id)

    def _get_profile_context(self, user_id: int) -> tuple[object | None, set[str], list[object]]:
        profile = self._get_profile(user_id)
        if not profile:
            return None, set(), []
        skills = self.profile_repo.list_skills_by_profile_id(profile.id)
        experiences = self.profile_repo.list_experiences_by_profile_id(profile.id)
        return profile, normalize_skills(skills), experiences

    def _get_normalized_user_skills(self, user_id: int) -> set[str]:
        profile = self._get_profile(user_id)
        if not profile:
            return set()
        skills = self.profile_repo.list_skills_by_profile_id(profile.id)
        return normalize_skills(skills)

    def _get_user_experiences(self, user_id: int):
        profile = self._get_profile(user_id)
        if not profile:
            return []
        return self.profile_repo.list_experiences_by_profile_id(profile.id)

    def _build_match_score_result(
        self,
        *,
        profile,
        normalized_user_skills: set[str],
        experiences,
        role,
    ) -> dict[str, object]:
        breakdown = {
            "skill_match":       calculate_skill_match_for_role(normalized_user_skills, role),
            "experience_match":  calculate_experience_match_for_role(profile, experiences, role),
            "education_match":   calculate_education_match_for_role(profile, role),
            "preferences_match": calculate_preferences_match_for_role(profile, role),
        }
        return {
            "total_score": calculate_weighted_match_score(breakdown),
            "breakdown":   breakdown,
            "skill_gaps":  detect_skill_gaps_for_role(normalized_user_skills, role),
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def calculate_skill_match(self, user_id: int, role_id: UUID) -> float:
        role = self._get_role_or_raise(role_id)
        return calculate_skill_match_for_role(self._get_normalized_user_skills(user_id), role)

    def detect_skill_gaps(self, user_id: int, role_id: UUID) -> list[dict[str, object]]:
        role = self._get_role_or_raise(role_id)
        return detect_skill_gaps_for_role(self._get_normalized_user_skills(user_id), role)

    def calculate_experience_match(self, user_id: int, role_id: UUID) -> float:
        role = self._get_role_or_raise(role_id)
        return calculate_experience_match_for_role(
            self._get_profile(user_id), self._get_user_experiences(user_id), role
        )

    def calculate_education_match(self, user_id: int, role_id: UUID) -> float:
        role = self._get_role_or_raise(role_id)
        return calculate_education_match_for_role(self._get_profile(user_id), role)

    def calculate_preferences_match(self, user_id: int, role_id: UUID) -> float:
        role = self._get_role_or_raise(role_id)
        return calculate_preferences_match_for_role(self._get_profile(user_id), role)

    def calculate_match_score(self, user_id: int, role_id: UUID) -> dict[str, object]:
        role = self._get_role_or_raise(role_id)
        profile, normalized_user_skills, experiences = self._get_profile_context(user_id)
        return self._build_match_score_result(
            profile=profile,
            normalized_user_skills=normalized_user_skills,
            experiences=experiences,
            role=role,
        )

    def calculate_and_cache_matches_for_user(self, user_id: int) -> dict[str, object]:
        roles = self.role_repo.list_available_roles()
        profile, normalized_user_skills, experiences = self._get_profile_context(user_id)
        existing = {
            mr.role_id: mr
            for mr in self.match_result_repo.list_by_user_id(user_id)
        }
        created_count = 0
        updated_count = 0
        results: list[dict[str, object]] = []

        for role in roles:
            calculated = self._build_match_score_result(
                profile=profile,
                normalized_user_skills=normalized_user_skills,
                experiences=experiences,
                role=role,
            )
            total_score = normalize_decimal(calculated["total_score"])
            existing_mr = existing.get(role.id)

            if existing_mr:
                existing_mr.total_score = total_score
                updated_count += 1
            else:
                mr = MatchResult(user_id=user_id, role_id=role.id, total_score=total_score)
                self.db.add(mr)
                existing[role.id] = mr
                created_count += 1

            results.append({
                "role_id":     str(role.id),
                "role_name":   role.name,
                "total_score": calculated["total_score"],
                "breakdown":   calculated["breakdown"],
                "skill_gaps":  calculated["skill_gaps"],
            })

        self.db.commit()

        return {
            "processed_roles": len(roles),
            "created":         created_count,
            "updated":         updated_count,
            "results":         results,
        }

    def get_cached_recommendations_for_user(self, user_id: int, limit: int = 10) -> list[MatchResult]:
        return self.match_result_repo.list_top_recommendations_by_user_id(user_id, limit=limit)
