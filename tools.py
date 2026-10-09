import math
from typing import Literal
from langchain_core.tools import tool
@tool
def calculator(a: float, b: float,
               operation: Literal["add", "subtract", "multiply", "divide"]) -> dict:
    """Calculate two finite numbers using the selected operation."""
    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError("Numbers must be finite")
    if operation == "add":
        value = a + b
    elif operation == "subtract":
        value = a - b
    elif operation == "multiply":
        value = a * b
    else:
        if b == 0:
            raise ValueError("Division by zero")
        value = a / b
    if not math.isfinite(value):
        raise ValueError("Result must be finite")
    return {"value": value}
@tool
def count_words(text: str) -> dict:
    """Count whitespace-separated units, not linguistic Vietnamese words.
    Input is limited to 4000 characters.
    """
    if len(text) > 4000:
        raise ValueError("Text is too long")
    return {"count": len(text.split())}
TOOLS = [calculator, count_words]
TOOL_MAP = {item.name: item for item in TOOLS}
