"""Learner assessment generation service."""

import json
import logging
import re
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.schemas.assessment import AssessmentResponse
from app.services.llm import build_chat_model

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 4096

ASSESSMENT_TEMPLATE: dict[str, Any] = {
    "title": "RAG readiness check",
    "instructions": "Answer honestly. These questions calibrate the generated learning path.",
    "questions": [
        {
            "id": "q1",
            "type": "single_choice",
            "prompt": "Which best describes your current experience with retrieval augmented generation?",
            "options": [
                {"id": "a", "text": "I have only heard the term."},
                {"id": "b", "text": "I understand the high-level idea."},
                {"id": "c", "text": "I have built or debugged a basic RAG flow."},
            ],
        },
        {
            "id": "q2",
            "type": "multiple_choice",
            "prompt": "Which parts have you worked with before?",
            "options": [
                {"id": "a", "text": "Chunking documents"},
                {"id": "b", "text": "Embeddings"},
                {"id": "c", "text": "Vector search"},
                {"id": "d", "text": "Prompt assembly"},
            ],
            "max_selections": 4,
        },
        {
            "id": "q6",
            "type": "free_text",
            "prompt": "Briefly describe what you want to be able to do after learning this.",
            "placeholder": "For example: build a support-doc chatbot with citations.",
            "max_words": 80,
        },
    ],
}

_ASSESSMENT_SYSTEM = f"""
You are an expert technical interviewer and curriculum designer.

Create a short diagnostic assessment for a learner before generating a learning
path. Return only valid JSON with this shape:

{json.dumps(ASSESSMENT_TEMPLATE, indent=2)}

Rules:
- The assessment measures what the learner already knows, what they have used,
  and how deep the generated course should go.
- Prefer selection questions. Use "single_choice" and "multiple_choice" for
  almost everything.
- Include at most one "free_text" question, and only when it captures a goal or
  constraint that options cannot capture.
- Do not include correct answers, scoring, explanations, or grading metadata.
- Question ids must be stable strings like "q1", "q2", "q3".
- Option ids must be stable lowercase strings like "a", "b", "c".
- Use topic-specific wording. Avoid generic learning-style questions.
- Keep options mutually distinct and useful for depth calibration.
"""

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


class AssessmentGenerationError(ValueError):
    """Raised when the model returns an assessment that cannot be validated."""


def _message_text(message: BaseMessage) -> str:
    """Return a message's content as plain text."""
    content = message.content
    return content if isinstance(content, str) else str(content)


def _extract_json_payload(text: str) -> str:
    """Extract the JSON payload from a plain or fenced model reply."""
    fenced = _JSON_FENCE.search(text)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    if start < 0:
        raise AssessmentGenerationError("LLM response did not include JSON")

    end = text.rfind("}")
    if end < start:
        raise AssessmentGenerationError("LLM response included incomplete JSON")

    return text[start : end + 1].strip()


def _parse_assessment_payload(topic: str, text: str) -> AssessmentResponse:
    """Parse and validate a model response into the public assessment schema."""
    try:
        payload = json.loads(_extract_json_payload(text))
    except json.JSONDecodeError as exc:
        raise AssessmentGenerationError("LLM response included invalid JSON") from exc

    if not isinstance(payload, dict):
        raise AssessmentGenerationError("LLM response JSON must be an object")

    try:
        return AssessmentResponse.model_validate({"topic": topic, **payload})
    except ValidationError as exc:
        raise AssessmentGenerationError("LLM response did not match the assessment schema") from exc


async def _generate_assessment(
    model: ChatOpenAI,
    topic: str,
    question_count: int,
) -> AssessmentResponse:
    """Ask the model to generate a diagnostic assessment for ``topic``."""
    reply = await model.ainvoke(
        [
            SystemMessage(content=_ASSESSMENT_SYSTEM),
            HumanMessage(
                content=(
                    f"Learning request: {topic}\n"
                    f"Generate exactly {question_count} diagnostic questions."
                )
            ),
        ]
    )
    text = _message_text(reply)
    if reply.response_metadata.get("finish_reason") == "length":
        logger.error("LLM output hit the %s token cap for topic %r", MAX_OUTPUT_TOKENS, topic)
        raise AssessmentGenerationError("LLM response was truncated before completion")
    try:
        return _parse_assessment_payload(topic, text)
    except AssessmentGenerationError:
        logger.error("Unusable LLM assessment for topic %r:\n%s", topic, text)
        raise


async def generate_assessment(topic: str, question_count: int = 6) -> AssessmentResponse:
    """Generate diagnostic questions for a learning request."""
    model = build_chat_model(streaming=False, max_tokens=MAX_OUTPUT_TOKENS, json_mode=True)
    return await _generate_assessment(model, topic, question_count)
