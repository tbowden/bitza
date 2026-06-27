from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """
    Accept either an email address or a username in ``identifier``.
    The service layer resolves which one was supplied.
    """

    identifier: str = Field(
        ...,
        description="Email address or username",
        min_length=1,
    )
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Returned on login and refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str
