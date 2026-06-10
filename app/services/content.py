"""Structured learning content generation service.

Turn a free-form learning request (e.g. ``"teach me RAG"``) into a validated
learning path made of frontend-friendly modules. The LLM fills a predefined
module template, while Pydantic keeps the API response predictable.
"""

import json
import logging
import re
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.schemas.content import ContentResponse
from app.services.llm import build_chat_model

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 16384

MODULE_TEMPLATE: dict[str, Any] = {
    "order": 1,
    "title": "A concise module title",
    "learning_objective": "What the learner will be able to do after this module",
    "estimated_minutes": 12,
    "blocks": [
        {
            "type": "markdown",
            "markdown": "A lesson section in Markdown: explanation, examples, code.",
        },
        {
            "type": "process",
            "title": "Name of the step-by-step workflow",
            "steps": [
                {"title": "First step", "description": "What to do and why"},
                {"title": "Second step", "description": "What to do and why"},
            ],
        },
        {
            "type": "single_choice_question",
            "question": "A knowledge-check question about this module",
            "options": ["First option", "Second option", "Third option"],
            "correct_option_index": 0,
            "explanation": "Why the correct option is right",
        },
        {
            "type": "reflection_review",
            "prompt": "A small exercise the learner can complete immediately",
            "review_criteria": [
                "How the learner can tell they understood the module",
                "A second observable check for understanding",
            ],
        },
    ],
}

_CONTENT_SYSTEM = f"""
You are an expert curriculum designer for technical professionals.

Create a focused web-learning experience from the learner's request. Return only
valid JSON with this shape:

{{
  "title": "Course-style title",
  "summary": "Two sentences describing the path and outcome.",
  "modules": [
    {json.dumps(MODULE_TEMPLATE, indent=6)}
  ]
}}

Each module's "blocks" array composes the lesson from these block types only:
- "markdown": the lesson body. Use Markdown freely (headings, lists, bold,
  fenced code) for explanations, examples, and case studies.
- "process": an ordered workflow or procedure with named steps. Use only when
  the content is genuinely sequential.
- "single_choice_question": a knowledge check with 3-4 plausible options and
  exactly one correct answer. "correct_option_index" is zero-based.
- "reflection_review": a hands-on exercise plus criteria the learner uses to
  self-review their answer.

Rules:
- Produce as many modules as the topic genuinely needs: a small topic may need
  only a few, a broad or deep topic may need more.
- Modules must be logically ordered from foundations to application.
- Each module needs at least three blocks: start with a markdown block, mix in
  the other types where they fit, and end with a single_choice_question or
  reflection_review so the learner checks their understanding.
- Each module must be useful on its own: explain the concept, include concrete
  examples, and give a practical exercise.
- Keep explanations concise but substantial enough that the learner can act.
- Use accurate, topic-specific content. Avoid generic study advice.
"""

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


class ContentGenerationError(ValueError):
    """Raised when the model returns content that cannot become a learning path."""


def _message_text(message: BaseMessage) -> str:
    """Return a message's content as plain text."""
    content = message.content
    return content if isinstance(content, str) else str(content)


def _extract_json_payload(text: str) -> str:
    """Extract the JSON payload from a plain or fenced model reply."""
    fenced = _JSON_FENCE.search(text)
    if fenced:
        return fenced.group(1).strip()

    start_candidates = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if not start_candidates:
        raise ContentGenerationError("LLM response did not include JSON")

    start = min(start_candidates)
    end = max(text.rfind("}"), text.rfind("]"))
    if end < start:
        raise ContentGenerationError("LLM response included incomplete JSON")

    return text[start : end + 1].strip()


def _parse_content_payload(topic: str, text: str) -> ContentResponse:
    """Parse and validate a model response into the public content schema."""
    try:
        payload = json.loads(_extract_json_payload(text))
    except json.JSONDecodeError as exc:
        raise ContentGenerationError("LLM response included invalid JSON") from exc

    if isinstance(payload, list):
        payload = {
            "topic": topic,
            "title": f"Learning path: {topic}",
            "summary": "A structured learning path generated for this topic.",
            "modules": payload,
        }
    elif isinstance(payload, dict):
        payload = {"topic": topic, **payload}
    else:
        raise ContentGenerationError("LLM response JSON must be an object or module list")

    try:
        return ContentResponse.model_validate(payload)
    except ValidationError as exc:
        raise ContentGenerationError("LLM response did not match the content schema") from exc


async def _generate_learning_path(model: ChatOpenAI, topic: str) -> ContentResponse:
    """Ask the model to fill the structured module template for ``topic``."""
    reply = await model.ainvoke(
        [
            SystemMessage(content=_CONTENT_SYSTEM),
            HumanMessage(content=f"Learning request: {topic}"),
        ]
    )
    text = _message_text(reply)
    if reply.response_metadata.get("finish_reason") == "length":
        logger.error("LLM output hit the %s token cap for topic %r", MAX_OUTPUT_TOKENS, topic)
        raise ContentGenerationError("LLM response was truncated before completion")
    try:
        return _parse_content_payload(topic, text)
    except ContentGenerationError:
        logger.error("Unusable LLM content for topic %r:\n%s", topic, text)
        raise


async def generate_content(topic: str) -> ContentResponse:
    """Generate structured learning modules for a topic.

    Args:
        topic: The free-form request, e.g. ``"teach me RAG"``.

    Returns:
        A title, summary, and ordered module list ready for frontend rendering.
    """
    model = build_chat_model(streaming=False, max_tokens=MAX_OUTPUT_TOKENS, json_mode=True)
    return await _generate_learning_path(model, topic)
