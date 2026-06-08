"""Structured learning content generation service.

Turn a free-form learning request (e.g. ``"teach me RAG"``) into a validated
learning path made of frontend-friendly modules. The LLM fills a predefined
module template, while Pydantic keeps the API response predictable.
"""

import json
import re
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.schemas.content import ContentResponse
from app.services.llm import build_chat_model

MAX_MODULES = 6

MODULE_TEMPLATE: dict[str, Any] = {
    "order": 1,
    "title": "A concise module title",
    "learning_objective": "What the learner will be able to do after this module",
    "estimated_minutes": 12,
    "explanation": "A clear, self-contained lesson body with practical detail",
    "key_points": [
        "A core idea the learner should remember",
        "Another important idea or distinction",
    ],
    "example": "A concrete example, scenario, command, or mini case study",
    "practice_prompt": "A small exercise the learner can complete immediately",
    "success_criteria": [
        "How the learner can tell they understood the module",
        "A second observable check for understanding",
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

Rules:
- Produce 4 to {MAX_MODULES} modules unless the topic is very small.
- Modules must be logically ordered from foundations to application.
- Each module must be useful on its own: explain the concept, include concrete
  examples, and give a practical exercise.
- Write for a web UI. Do not include markdown headings, code fences, or styling
  instructions.
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
    return _parse_content_payload(topic, _message_text(reply))


async def generate_content(topic: str) -> ContentResponse:
    """Generate structured learning modules for a topic.

    Args:
        topic: The free-form request, e.g. ``"teach me RAG"``.

    Returns:
        A title, summary, and ordered module list ready for frontend rendering.
    """
    model = build_chat_model(streaming=False)
    return await _generate_learning_path(model, topic)
