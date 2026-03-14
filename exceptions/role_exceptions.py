class RoleError(Exception):
    default_message = "Role error"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class RoleNotFoundError(RoleError):
    default_message = "Role not found"
