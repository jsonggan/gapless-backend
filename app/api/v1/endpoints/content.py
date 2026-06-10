"""Content generation endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentActiveUserDep, DBDep
from app.core.config import settings
from app.crud.learning_path import learning_path as learning_path_crud
from app.schemas.content import ContentRequest, ContentResponse
from app.services.content import ContentGenerationError, generate_content

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=ContentResponse)
async def generate(
    db: DBDep,
    current_user: CurrentActiveUserDep,
    request: ContentRequest,
) -> ContentResponse:
    """Generate structured learning modules for a topic."""
    if not settings.KIMI_API_KEY:
        raise HTTPException(status_code=503, detail="LLM service is not configured")

    try:
        content = await generate_content(request.topic)
    except ContentGenerationError as exc:
        logger.exception("Content generation failed for topic %r", request.topic)
        raise HTTPException(status_code=502, detail=f"LLM returned invalid content: {exc}") from exc

    saved = await learning_path_crud.create_from_content(
        db,
        user_id=current_user.id,
        content=content,
    )
    return ContentResponse.model_validate(saved)
