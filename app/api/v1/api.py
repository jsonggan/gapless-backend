"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import assessments, auth, content, learning_paths, llm, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(
    learning_paths.router,
    prefix="/learning-paths",
    tags=["learning-paths"],
)
