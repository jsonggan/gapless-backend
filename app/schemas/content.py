"""Content generation Pydantic schemas."""

from pydantic import BaseModel, Field


class ContentRequest(BaseModel):
    """Request to generate learning content for a topic."""

    topic: str = Field(min_length=1, description="What to learn, e.g. 'teach me RAG'.")


class ContentSection(BaseModel):
    """One section of generated content: an outline title and its body text."""

    title: str
    content: str


class ContentResponse(BaseModel):
    """Generated content: the outline titles paired with their written content."""

    topic: str
    sections: list[ContentSection]
