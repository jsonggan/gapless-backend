"""Content generation Pydantic schemas."""

from pydantic import BaseModel, ConfigDict, Field


class ContentRequest(BaseModel):
    """Request to generate learning content for a topic."""

    topic: str = Field(min_length=1, description="What to learn, e.g. 'teach me RAG'.")


class ContentModule(BaseModel):
    """A structured learning module the frontend can render into an experience."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    order: int = Field(ge=1)
    title: str
    learning_objective: str
    estimated_minutes: int = Field(ge=1)
    explanation: str
    key_points: list[str]
    example: str
    practice_prompt: str
    success_criteria: list[str]


class ContentResponse(BaseModel):
    """Generated learning path content for a web learning experience."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    topic: str
    title: str
    summary: str
    modules: list[ContentModule] = Field(min_length=1)
