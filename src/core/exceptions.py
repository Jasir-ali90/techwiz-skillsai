class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthError(AppError):
    status_code = 401
    code = "auth_error"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class ValidationFailedError(AppError):
    status_code = 422
    code = "document_validation_failed"