class TechnologyError(Exception):
    default_message = "Technology error"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class TechnologyNotFoundError(TechnologyError):
    default_message = "Technology not found"


class TechnologyAuthorizationError(TechnologyError):
    default_message = "Admin privileges are required"


class TechnologyValidationError(TechnologyError):
    default_message = "Invalid technology data"


class TechnologyInUseError(TechnologyError):
    default_message = "Technology is in use by one or more roles"
