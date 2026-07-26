from fastapi import HTTPException, status


class InvalidCredentialsError(HTTPException):
    """Wrong username/password or unrecognised identifier."""

    def __init__(self, detail: str = "Invalid credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidTokenError(HTTPException):
    """JWT is missing, malformed, expired, or the wrong type."""

    def __init__(self, detail: str = "Invalid or expired token") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class RevokedTokenError(HTTPException):
    """Token exists in DB but has been revoked (logout / rotation)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )


class UserSuspendedError(HTTPException):
    """User account exists but is_active=False."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is suspended",
        )


class PermissionDeniedError(HTTPException):
    """Authenticated user lacks the required role/privilege."""

    def __init__(self, detail: str = "Permission denied") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class UserNotFoundError(HTTPException):
    def __init__(self, detail: str = "User not found") -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class ConflictError(HTTPException):
    """Uniqueness violation (duplicate email, username, etc.)."""

    def __init__(self, detail: str = "Resource already exists") -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class SuperuserExistsError(HTTPException):
    """Attempted to create a second superuser."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="A superuser already exists. Use the CLI to manage the superuser account.",
        )


class RootBitzaExistsError(HTTPException):
    """Attempted to create a second root bitza via the CLI."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="A root bitza already exists. There can only be one — see the CLI's "
            "create-root command output for its details.",
        )


class RootBitzaProtectedError(HTTPException):
    """
    Attempted to delete, retire, or move the single root bitza. Unlike
    every other permission floor in this app (which is role-based — "only
    admins may do X"), this one is unconditional: it applies regardless of
    who's asking, including a superuser. The root is a structural anchor,
    not an ordinary record with elevated protection.
    """

    def __init__(self, detail: str = "The root bitza is protected and cannot be changed this way.") -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )
