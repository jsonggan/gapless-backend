"""FastAPI dependency injection utilities."""

from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.crud.user import user as user_crud
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole
from app.schemas.user import UserPublic

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        yield session


DBDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]


async def get_current_user(token: TokenDep, db: DBDep) -> User:
    """Validate access token and return current user."""
    payload = decode_access_token(token.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(user_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = await user_crud.get(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(current_user: CurrentUserDep) -> User:
    """Ensure the current user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


CurrentActiveUserDep = Annotated[User, Depends(get_current_active_user)]


def require_role(*roles: UserRole) -> Any:
    """Dependency factory that restricts access to users with specified roles."""

    async def role_checker(current_user: CurrentActiveUserDep) -> User:
        if current_user.role not in {r.value for r in roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return Depends(role_checker)


def require_admin() -> Any:
    """Dependency that restricts access to admin users."""
    return require_role(UserRole.ADMIN)


def to_public(user: User) -> UserPublic:
    """Convert a User ORM instance to a public schema."""
    return UserPublic.model_validate(user)
