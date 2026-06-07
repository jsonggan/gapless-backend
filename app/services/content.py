"""Content generation service.

Turn a free-form learning request (e.g. "teach me RAG") into a simple outline
-- the *content list* -- and then plain-text content for each section. This is a
single, non-streaming response: we plan the outline in one model call, then fill
in every section concurrently.

As this grows, prefer streaming and richer formatting; for now plain text and a
final response keep the surface area small.
"""

import asyncio
import re

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.schemas.content import ContentResponse, ContentSection
from app.services.llm import build_chat_model

# Keep generated guides small and focused for now.
MAX_SECTIONS = 7

_OUTLINE_SYSTEM = (
    "You are a curriculum planner. Given a topic a learner wants to understand, "
    "produce a concise, logically ordered outline that teaches it from the ground "
    f"up. Reply with at most {MAX_SECTIONS} section titles, one per line, with no "
    "numbering, bullets, or extra commentary."
)

_CONTENT_SYSTEM = (
    "You are a clear, concise technical writer. Given an overall topic and one "
    "section title, write a short plain-text explanation of just that section "
    "(a few short paragraphs). Do not add headings, markdown, or a preamble."
)

# Leading list markers we strip from outline lines: "1. ", "2) ", "- ", "* ", "# ".
_LIST_MARKER = re.compile(r"^\s*(?:[-*#]+|\d+[.)])\s*")


def _message_text(message: BaseMessage) -> str:
    """Return a message's content as plain text."""
    content = message.content
    return content if isinstance(content, str) else str(content)


def _parse_outline(text: str) -> list[str]:
    """Parse the model's outline reply into a clean list of section titles."""
    titles: list[str] = []
    for line in text.splitlines():
        title = _LIST_MARKER.sub("", line).strip()
        if title:
            titles.append(title)
    return titles[:MAX_SECTIONS]


async def _generate_outline(model: ChatOpenAI, topic: str) -> list[str]:
    """Ask the model for an ordered list of section titles for ``topic``."""
    reply = await model.ainvoke(
        [SystemMessage(content=_OUTLINE_SYSTEM), HumanMessage(content=topic)]
    )
    return _parse_outline(_message_text(reply))


async def _generate_section(model: ChatOpenAI, topic: str, title: str) -> ContentSection:
    """Generate the plain-text body for a single section ``title``."""
    reply = await model.ainvoke(
        [
            SystemMessage(content=_CONTENT_SYSTEM),
            HumanMessage(content=f"Topic: {topic}\nSection: {title}"),
        ]
    )
    return ContentSection(title=title, content=_message_text(reply).strip())


async def generate_content(topic: str) -> ContentResponse:
    """Generate an outline and plain-text content for a learning topic.

    Args:
        topic: The free-form request, e.g. ``"teach me RAG"``.

    Returns:
        The topic alongside its generated sections (outline title + body).
    """
    model = build_chat_model(streaming=False)
    titles = await _generate_outline(model, topic)
    sections = await asyncio.gather(*(_generate_section(model, topic, title) for title in titles))
    return ContentResponse(topic=topic, sections=list(sections))
