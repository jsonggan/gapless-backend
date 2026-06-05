"""User Pydantic schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    """Base user schema with shared attributes."""

    email: EmailStr
    username: str
    full_name: str | None = None
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str


class UserUpdate(BaseModel):
    """Schema for updating an existing user."""

    email: EmailStr | None = None
    username: str | None = None
    full_name: str | None = None
    password: str | None = None
    is_active: bool | None = None


class UserPublic(UserBase):
    """Schema for public user data (returned in API responses)."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class UserInDB(UserPublic):
    """Schema for user data stored in the database."""

    hashed_password: str
