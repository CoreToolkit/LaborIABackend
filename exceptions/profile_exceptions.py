class ProfileError(Exception):
    default_message = "Profile error"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class ProfileAlreadyExistsError(ProfileError):
    default_message = "User already has a profile"


class ProfileNotFoundError(ProfileError):
    default_message = "Profile not found"


class ProfileValidationError(ProfileError):
    default_message = "Invalid profile data"


class ExperienceNotFoundError(ProfileError):
    default_message = "Experience not found"


class ExperienceValidationError(ProfileError):
    default_message = "Invalid experience data"
