class InterviewSessionError(Exception):
    default_message = "Interview session error"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class InterviewSessionNotFoundError(InterviewSessionError):
    default_message = "Interview session not found"
