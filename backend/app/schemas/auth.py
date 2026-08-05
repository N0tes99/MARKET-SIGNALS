"""Auth request/response schemas."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


class RegisterRequest(BaseModel):
    """Create a new account."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not USERNAME_RE.match(value):
            raise ValueError("Username must be 3–32 chars: letters, numbers, underscore")
        return value


class LoginRequest(BaseModel):
    """Email/password login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserSchema(BaseModel):
    """Public user profile."""

    id: uuid.UUID
    email: EmailStr
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}
