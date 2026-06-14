"""AI feedback service for learning path free-text answers."""

import json
import logging
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.schemas.learning_path import LearningPathFeedbackResponse
from app.services.llm import build_chat_model

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 2048

FEEDBACK_TEMPLATE: dict[str, Any] = {
    "feedback": "A concise, supportive explanation of how well the answer addresses the question.",
    "strengths": ["One specific thing the learner got right."],
    "improvements": ["One specific correction or missing idea to add."],
    "suggested_answer": "A strong answer the learner can compare against.",
}

_FEEDBACK_SYSTEM = f"""
You are a precise, encouraging technical tutor.

Review a learner's free-text answer using the supplied lesson context. Return
only valid JSON with this shape:

{json.dumps(FEEDBACK_TEMPLATE, indent=2)}

Rules:
- Judge only against the provided context and question.
- Be specific about what is correct, incomplete, or incorrect.
- Keep "feedback" to 2-4 sentences.
- Keep each strength and improvement short and actionable.
- If the learner is mostly wrong, still identify any useful partial
  understanding before correcting it.
- "suggested_answer" should be complete but concise.
"""


class LearningFeedbackGenerationError(ValueError):
    """Raised when the model returns feedback that cannot be validated."""


def _message_text(message: BaseMessage) -> str:
    """Return a message's content as plain text."""
    content = message.content
    return content if isinstance(content, str) else str(content)


def _extract_json_payload(text: str) -> str:
    """Extract the JSON payload from a plain or fenced model reply."""
    stripped = text.strip()
    decoder = json.JSONDecoder()

    for index, char in enumerate(stripped):
        if char != "{":
            continue

        try:
            _, end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue

        return stripped[index : index + end].strip()

    raise LearningFeedbackGenerationError("LLM response did not include JSON")


def _parse_feedback_payload(text: str) -> LearningPathFeedbackResponse:
    """Parse and validate a model response into the public feedback schema."""
    try:
        payload = json.loads(_extract_json_payload(text))
    except json.JSONDecodeError as exc:
        raise LearningFeedbackGenerationError("LLM response included invalid JSON") from exc

    if not isinstance(payload, dict):
        raise LearningFeedbackGenerationError("LLM response JSON must be an object")

    try:
        return LearningPathFeedbackResponse.model_validate(payload)
    except ValidationError as exc:
        raise LearningFeedbackGenerationError(
            "LLM response did not match the feedback schema"
        ) from exc


async def _generate_learning_path_feedback(
    model: ChatOpenAI,
    *,
    context: str,
    question: str,
    answer: str,
) -> LearningPathFeedbackResponse:
    """Ask the model to review a learner's answer."""
    reply = await model.ainvoke(
        [
            SystemMessage(content=_FEEDBACK_SYSTEM),
            HumanMessage(
                content=(
                    f"Context:\n{context}\n\nQuestion:\n{question}\n\nLearner answer:\n{answer}"
                )
            ),
        ]
    )
    text = _message_text(reply)
    if reply.response_metadata.get("finish_reason") == "length":
        logger.error("LLM feedback output hit the %s token cap", MAX_OUTPUT_TOKENS)
        raise LearningFeedbackGenerationError("LLM response was truncated before completion")
    try:
        return _parse_feedback_payload(text)
    except LearningFeedbackGenerationError:
        logger.error(
            "Unusable LLM feedback for question %r and answer %r:\n%s",
            question,
            answer,
            text,
        )
        raise


async def generate_learning_path_feedback(
    *,
    context: str,
    question: str,
    answer: str,
) -> LearningPathFeedbackResponse:
    """Generate structured tutor feedback for a free-text learning answer."""
    model = build_chat_model(streaming=False, max_tokens=MAX_OUTPUT_TOKENS, json_mode=True)
    return await _generate_learning_path_feedback(
        model,
        context=context,
        question=question,
        answer=answer,
    )
