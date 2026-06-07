"""Central registry of tools available to agents.

Register new tools here (or via ``register``) so the runner can discover and
bind them. Keeping a single source of truth makes it straightforward to scope
tools per-agent later (e.g. ``get_tools(names=...)``) as the system grows.
"""

from langchain_core.tools import BaseTool

from app.agents.tools.math import add

# Ordered list of every tool the agents can use.
_TOOLS: list[BaseTool] = [add]


def register(tool: BaseTool) -> None:
    """Add a tool to the global registry (idempotent by name)."""
    if any(existing.name == tool.name for existing in _TOOLS):
        return
    _TOOLS.append(tool)


def get_tools() -> list[BaseTool]:
    """Return all registered tools."""
    return list(_TOOLS)


def get_tool(name: str) -> BaseTool | None:
    """Return a registered tool by name, or ``None`` if not found."""
    return next((tool for tool in _TOOLS if tool.name == name), None)
