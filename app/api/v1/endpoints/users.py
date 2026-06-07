"""User endpoints."""

from fastapi import APIRouter

from app.api.deps import (
    CurrentActiveUserDep,
    DBDep,
    require_role,
    to_public,
)
from app.crud.user import user as user_crud
from app.models.user import User, UserRole
from app.schemas.user import UserPublic, UserUpdate

router = APIRouter()


@router.get("/", response_model=list[UserPublic])
async def list_users(
    db: DBDep,
    current_user: CurrentActiveUserDep,
    _admin: User = require_role(UserRole.ADMIN),  # noqa: B008
) -> list[UserPublic]:
    """List all users (admin only)."""
    users = await user_crud.get_multi(db)
    return [to_public(u) for u in users]


@router.get("/me", response_model=UserPublic)
async def read_user_me(current_user: CurrentActiveUserDep) -> UserPublic:
    """Get current authenticated user."""
    return to_public(current_user)


@router.patch("/me", response_model=UserPublic)
async def update_user_me(
    db: DBDep,
    current_user: CurrentActiveUserDep,
    obj_in: UserUpdate,
) -> UserPublic:
    """Update current authenticated user."""
    updated = await user_crud.update(db, current_user, obj_in)
    return to_public(updated)
