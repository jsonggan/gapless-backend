"""Math tools for agents."""

from langchain_core.tools import tool


@tool
def add(a: float, b: float) -> float:
    """Add two numbers together and return their sum.

    Args:
        a: The first number.
        b: The second number.
    """
    return a + b
