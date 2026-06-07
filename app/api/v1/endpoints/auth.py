"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DBDep, to_public
from app.core.security import create_access_token, verify_password
from app.crud.user import user as user_crud
from app.schemas.auth import LoginRequest, RegisterRequest, Token
from app.schemas.user import UserCreate, UserPublic

router = APIRouter()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(db: DBDep, obj_in: RegisterRequest) -> UserPublic:
    """Register a new user."""
    existing_email = await user_crud.get_by_email(db, obj_in.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    existing_username = await user_crud.get_by_username(db, obj_in.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )
    user_in = UserCreate(
        email=obj_in.email,
        username=obj_in.username,
        password=obj_in.password,
        full_name=obj_in.full_name,
    )
    user = await user_crud.create(db, user_in)
    return to_public(user)


@router.post("/login", response_model=Token)
async def login(db: DBDep, obj_in: LoginRequest) -> Token:
    """Authenticate and return a JWT token."""
    user = await user_crud.get_by_email(db, obj_in.email)
    if user is None or not verify_password(obj_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token)
