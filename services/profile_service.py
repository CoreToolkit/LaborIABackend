from datetime import date
from sqlalchemy.orm import Session
from pydantic import ValidationError

from exceptions.profile_exceptions import (
    ExperienceNotFoundError,
    ExperienceValidationError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileValidationError,
)
from models.experience import Experience
from models.profile import EmploymentType, EnglishLevel, Profile
from repositories.profile_repository import ProfileRepository
from schemas.experience import ExperienceCreate, ExperienceUpdate


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

    @staticmethod
    def _extract_experience_validation_message(exc: ValidationError) -> str:
        first_error = exc.errors()[0]
        message = first_error.get("msg", ExperienceValidationError.default_message)
        if message.startswith("Value error, "):
            return message.removeprefix("Value error, ")
        return message

    @classmethod
    def _validate_experience_resolved_data(cls, data: dict) -> None:
        try:
            ExperienceCreate.model_validate(data)
        except ValidationError as exc:
            raise ExperienceValidationError(cls._extract_experience_validation_message(exc)) from exc

    def _get_required_profile(self, user_id: int) -> Profile:
        profile = self.repo.get_by_user_id(user_id)
        if not profile:
            raise ProfileNotFoundError()
        return profile

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
        profile = self._get_required_profile(user_id)

        self.repo.delete(profile)

    def list_experiences(self, user_id: int) -> list[Experience]:
        profile = self._get_required_profile(user_id)
        return self.repo.list_experiences_by_profile_id(profile.id)

    def create_experience(self, user_id: int, experience_data: ExperienceCreate) -> Experience:
        profile = self._get_required_profile(user_id)
        create_data = experience_data.model_dump()
        create_data["profile_id"] = profile.id
        return self.repo.create_experience(create_data)

    def update_experience(
        self,
        user_id: int,
        experience_id: int,
        experience_data: ExperienceUpdate,
    ) -> Experience:
        profile = self._get_required_profile(user_id)
        experience = self.repo.get_experience_by_id_and_profile_id(experience_id, profile.id)
        if not experience:
            raise ExperienceNotFoundError()

        update_data = experience_data.model_dump(exclude_unset=True)
        if update_data.get("currently_working") is True and "end_date" not in update_data:
            update_data["end_date"] = None

        resolved_data = {
            "position": update_data.get("position", experience.position),
            "company": update_data.get("company", experience.company),
            "start_date": update_data.get("start_date", experience.start_date),
            "end_date": update_data.get("end_date", experience.end_date),
            "description": update_data.get("description", experience.description),
            "currently_working": update_data.get("currently_working", experience.currently_working),
        }
        self._validate_experience_resolved_data(resolved_data)

        return self.repo.update_experience(experience, update_data)

    def delete_experience(self, user_id: int, experience_id: int) -> None:
        profile = self._get_required_profile(user_id)
        experience = self.repo.get_experience_by_id_and_profile_id(experience_id, profile.id)
        if not experience:
            raise ExperienceNotFoundError()

        self.repo.delete_experience(experience)
