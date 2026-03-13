from sqlalchemy.orm import Session
from datetime import date

from exceptions.profile_exceptions import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileValidationError,
)
from models.profile import EmploymentType, EnglishLevel, Profile
from repositories.profile_repository import ProfileRepository


class ProfileService:
    def __init__(self, db: Session):
        self.repo = ProfileRepository(db)

    @staticmethod
    def _prepare_profile_data(data: dict) -> dict:
        prepared = dict(data)

        # Accept common typo from frontend and map to the actual DB field.
        if "referred_employment_type" in prepared and "preferred_employment_type" not in prepared:
            prepared["preferred_employment_type"] = prepared.pop("referred_employment_type")

        allowed_fields = {
            "full_name",
            "career",
            "university",
            "graduation_date",
            "description",
            "english_level",
            "preferred_location",
            "preferred_employment_type",
            "salary_expectation",
            "user_id",
        }
        prepared = {key: value for key, value in prepared.items() if key in allowed_fields}

        if prepared.get("english_level") is not None:
            try:
                prepared["english_level"] = EnglishLevel(prepared["english_level"])
            except ValueError as exc:
                valid_values = ", ".join(level.value for level in EnglishLevel)
                raise ProfileValidationError(f"Invalid english_level. Valid values: {valid_values}") from exc

        if prepared.get("preferred_employment_type") is not None:
            try:
                prepared["preferred_employment_type"] = EmploymentType(prepared["preferred_employment_type"])
            except ValueError as exc:
                valid_values = ", ".join(item.value for item in EmploymentType)
                raise ProfileValidationError(
                    f"Invalid preferred_employment_type. Valid values: {valid_values}"
                ) from exc

        if prepared.get("graduation_date") is not None and isinstance(prepared["graduation_date"], str):
            try:
                prepared["graduation_date"] = date.fromisoformat(prepared["graduation_date"])
            except ValueError as exc:
                raise ProfileValidationError("Invalid graduation_date. Use YYYY-MM-DD format") from exc

        return prepared

    def get_profile_by_user_id(self, user_id: int) -> Profile | None:
        return self.repo.get_by_user_id(user_id)

    def create_profile(self, user_id: int, profile_data: dict) -> Profile:
        existing_profile = self.repo.get_by_user_id(user_id)
        if existing_profile:
            raise ProfileAlreadyExistsError()
        profile_data = self._prepare_profile_data(profile_data)
        profile_data["user_id"] = user_id

        return self.repo.create(profile_data)

    def update_profile(self, user_id: int, update_data: dict) -> Profile:
        profile = self.repo.get_by_user_id(user_id)
        if not profile:
            raise ProfileNotFoundError()

        update_data = self._prepare_profile_data(update_data)

        return self.repo.update(profile, update_data)

    def delete_profile(self, user_id: int) -> None:
        profile = self.repo.get_by_user_id(user_id)
        if not profile:
            raise ProfileNotFoundError()

        self.repo.delete(profile)
