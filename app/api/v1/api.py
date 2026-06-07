"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import agents, auth, content, llm, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
