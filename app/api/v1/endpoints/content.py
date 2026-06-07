"""Content generation endpoints."""

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentActiveUserDep
from app.core.config import settings
from app.schemas.content import ContentRequest, ContentResponse
from app.services.content import generate_content

router = APIRouter()


@router.post("/generate", response_model=ContentResponse)
async def generate(
    current_user: CurrentActiveUserDep,
    request: ContentRequest,
) -> ContentResponse:
    """Generate a content outline and plain-text content for a topic."""
    if not settings.KIMI_API_KEY:
        raise HTTPException(status_code=503, detail="LLM service is not configured")

    return await generate_content(request.topic)
