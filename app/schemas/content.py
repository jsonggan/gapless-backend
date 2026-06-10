"""Content generation Pydantic schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, model_validator


class ContentRequest(BaseModel):
    """Request to generate learning content for a topic."""

    topic: str = Field(min_length=1, description="What to learn, e.g. 'teach me RAG'.")


class MarkdownBlock(BaseModel):
    """A markdown-rendered lesson section."""

    type: Literal["markdown"] = "markdown"
    markdown: str = Field(min_length=1)


class ProcessStep(BaseModel):
    """A single step inside a process block."""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ProcessBlock(BaseModel):
    """An ordered step-by-step process or workflow."""

    type: Literal["process"] = "process"
    title: str = Field(min_length=1)
    steps: list[ProcessStep] = Field(min_length=1)


class SingleChoiceQuestionBlock(BaseModel):
    """A knowledge-check question with exactly one correct option."""

    type: Literal["single_choice_question"] = "single_choice_question"
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=2)
    correct_option_index: int = Field(ge=0)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_correct_option_index(self) -> "SingleChoiceQuestionBlock":
        """Ensure the correct option index points at an existing option."""
        if self.correct_option_index >= len(self.options):
            raise ValueError("correct_option_index must reference an option")
        return self


class ReflectionReviewBlock(BaseModel):
    """An open exercise the learner self-reviews against criteria."""

    type: Literal["reflection_review"] = "reflection_review"
    prompt: str = Field(min_length=1)
    review_criteria: list[str] = Field(min_length=1)


LessonBlock = Annotated[
    MarkdownBlock | ProcessBlock | SingleChoiceQuestionBlock | ReflectionReviewBlock,
    Field(discriminator="type"),
]

lesson_block_adapter: TypeAdapter[LessonBlock] = TypeAdapter(LessonBlock)


class ContentModule(BaseModel):
    """A structured learning module the frontend can render into an experience."""

    id: int | None = None
    order: int = Field(ge=1)
    title: str
    learning_objective: str
    estimated_minutes: int = Field(ge=1)
    blocks: list[LessonBlock] = Field(min_length=1)


class ContentResponse(BaseModel):
    """Generated learning path content for a web learning experience."""

    id: int | None = None
    topic: str
    title: str
    summary: str
    modules: list[ContentModule] = Field(min_length=1)
