"""Utilities for parsing LLM responses: extract Python code, JSON objects, and strip Markdown fences."""

import json
import re
from typing import Any


def clean_code(llm_response: str) -> str:
    """Extract a Python snippet from common Markdown fenced-code responses."""

    pattern = r"```(?:python|py)?\s*(.*?)\s*```"
    match = re.search(pattern, llm_response, re.DOTALL)

    if match:
        return match.group(1)

    # Fallback: strip leading/trailing fences, then try regex again
    # (LLM may have wrapped code in ``` with extra prefatory text)
    stripped = strip_fences(llm_response)
    match = re.search(pattern, stripped, re.DOTALL)
    if match:
        return match.group(1)

    # Last resort: return stripped text without global backtick replacement
    return stripped


def strip_fences(text: str) -> str:
    """Strip Markdown code fences (``` ... ```) from LLM response text.

    Returns the text with leading/trailing triple-backtick lines removed
    and surrounding whitespace stripped.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    return cleaned


def extract_json(raw: str) -> dict[str, Any]:
    """Extract a JSON object from an LLM response string.

    Handles:
    - Clean JSON
    - Markdown-fenced JSON (```json { ... } ``` or ``` { ... } ```)
    - JSON embedded in mixed text (regex extraction of first { ... } block)

    Raises:
        ValueError: No valid JSON object could be extracted.
    """
    cleaned = strip_fences(raw)
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
        raise ValueError(f"Extracted JSON is not a dict (got {type(result).__name__})")
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
            raise ValueError(f"Extracted JSON from regex is not a dict (got {type(result).__name__})")
        raise ValueError(f"No JSON object found in LLM response: {cleaned[:200]}")
