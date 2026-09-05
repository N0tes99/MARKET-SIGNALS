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


class VerifyEmailRequest(BaseModel):
    """Confirm email with token from the verification link."""

    token: str = Field(min_length=16, max_length=256)


class ResendVerificationRequest(BaseModel):
    """Resend verification email by address (pre-login) or authenticated user."""

    email: EmailStr | None = None


class ForgotPasswordRequest(BaseModel):
    """Request a password-reset email."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Set a new password using the email reset token."""

    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    """Change password while authenticated (required for admin)."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserSchema(BaseModel):
    """Public user profile."""

    id: uuid.UUID
    email: EmailStr
    username: str
    email_verified: bool
    created_at: datetime
    is_admin: bool = False

    model_config = {"from_attributes": True}
