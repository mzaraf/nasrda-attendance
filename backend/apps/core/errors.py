from rest_framework.exceptions import APIException


class DomainError(APIException):
    """Structured error: the frontend switches on `code` to show a specific message."""
    status_code = 400

    def __init__(self, code: str, message: str, status_code: int | None = None):
        if status_code:
            self.status_code = status_code
        self.detail = {"code": code, "message": message}