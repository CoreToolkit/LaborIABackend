class RoleError(Exception):
    default_message = "Role error"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class RoleNotFoundError(RoleError):
    default_message = "Role not found"


class RoleAuthorizationError(RoleError):
    default_message = "Admin privileges are required"


class RoleValidationError(RoleError):
    default_message = "Invalid role data"
