"""Authentication Pydantic schemas."""

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """JWT token response schema."""

    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request schema."""

    email: EmailStr
    username: str
    password: str
    full_name: str | None = None
