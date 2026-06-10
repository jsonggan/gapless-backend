"""Assessment generation Pydantic schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class AssessmentRequest(BaseModel):
    """Request to generate a learner knowledge assessment."""

    topic: str = Field(
        min_length=1,
        description="What the user wants to learn, e.g. 'teach me RAG'.",
    )
    question_count: int = Field(
        default=6,
        ge=3,
        le=10,
        description="How many diagnostic questions to generate.",
    )


class AssessmentOption(BaseModel):
    """A selectable answer option for an assessment question."""

    id: str = Field(min_length=1, description="Stable option id, e.g. 'a'.")
    text: str = Field(min_length=1)


class _SelectionQuestion(BaseModel):
    """Shared validation for selection-based questions."""

    id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    options: list[AssessmentOption] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_unique_option_ids(self) -> "_SelectionQuestion":
        """Ensure option ids are unique within a question."""
        option_ids = [option.id for option in self.options]
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("option ids must be unique within a question")
        return self


class SingleChoiceAssessmentQuestion(_SelectionQuestion):
    """A diagnostic question where the learner picks exactly one option."""

    type: Literal["single_choice"] = "single_choice"


class MultipleChoiceAssessmentQuestion(_SelectionQuestion):
    """A diagnostic question where the learner may pick several options."""

    type: Literal["multiple_choice"] = "multiple_choice"
    max_selections: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_max_selections(self) -> "MultipleChoiceAssessmentQuestion":
        """Ensure the selection cap can be satisfied by the available options."""
        if self.max_selections is not None and self.max_selections > len(self.options):
            raise ValueError("max_selections must not exceed the number of options")
        return self


class FreeTextAssessmentQuestion(BaseModel):
    """A short free-text diagnostic question."""

    type: Literal["free_text"] = "free_text"
    id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    placeholder: str | None = None
    max_words: int = Field(default=80, ge=1, le=200)


AssessmentQuestion = Annotated[
    SingleChoiceAssessmentQuestion | MultipleChoiceAssessmentQuestion | FreeTextAssessmentQuestion,
    Field(discriminator="type"),
]


class AssessmentResponse(BaseModel):
    """Generated diagnostic assessment for calibrating a learning path."""

    topic: str = Field(min_length=1)
    title: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    questions: list[AssessmentQuestion] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_question_mix(self) -> "AssessmentResponse":
        """Keep question ids unique and prefer selection questions."""
        question_ids = [question.id for question in self.questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("question ids must be unique")

        free_text_count = sum(question.type == "free_text" for question in self.questions)
        if free_text_count > 1:
            raise ValueError("assessment should include at most one free_text question")
        return self
