"""Authentication schemas"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Annotated, ClassVar


class ValidatePassword(BaseModel):
    SPECIAL_CHARS: ClassVar[frozenset] = frozenset(' !@#$%^&*()_+-=[]{};\':"|,.<>/?\\')
    password: Annotated[str, Field(min_length = 8, max_length = 256)]

    @field_validator('password')
    @classmethod
    def validate(cls, v: str) -> bool:
        errors = []
        if not any(c.islower() for c in v):
            errors.append('No lower case letter')
        if not any(c.isupper() for c in v):
            errors.append('No upper case letter')
        if not any(c.isdigit() for c in v):
            errors.append('No digit(s) [0-9]')
        if not any(c in cls.SPECIAL_CHARS for c in v):
            errors.append('No special chars [ !@#$%^&*()_+-=[]{};\':"|,.<>/?]')



class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

