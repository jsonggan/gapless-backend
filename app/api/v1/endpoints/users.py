"""User endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_users() -> list[dict[str, str]]:
    """List all users (placeholder)."""
    return []


@router.get("/me")
async def read_user_me() -> dict[str, str]:
    """Get current user (placeholder)."""
    return {"username": "currentuser"}
