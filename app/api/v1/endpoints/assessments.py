"""Assessment generation endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentActiveUserDep
from app.core.config import settings
from app.schemas.assessment import AssessmentRequest, AssessmentResponse
from app.services.assessment import AssessmentGenerationError, generate_assessment

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=AssessmentResponse)
async def generate(
    current_user: CurrentActiveUserDep,
    request: AssessmentRequest,
) -> AssessmentResponse:
    """Generate a diagnostic assessment for a learning topic."""
    if not settings.KIMI_API_KEY:
        raise HTTPException(status_code=503, detail="LLM service is not configured")

    try:
        return await generate_assessment(
            topic=request.topic,
            question_count=request.question_count,
        )
    except AssessmentGenerationError as exc:
        logger.exception("Assessment generation failed for topic %r", request.topic)
        raise HTTPException(
            status_code=502,
            detail=f"LLM returned invalid assessment: {exc}",
        ) from exc
