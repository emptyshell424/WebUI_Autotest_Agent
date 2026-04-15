import re


def clean_code(llm_response: str) -> str:
    """Extract a Python snippet from common Markdown fenced-code responses."""

    pattern = r"```(?:python|py)?\s*(.*?)\s*```"
    match = re.search(pattern, llm_response, re.DOTALL)

    if match:
        return match.group(1)

    return (
        llm_response.replace("```python", "")
        .replace("```py", "")
        .replace("```", "")
        .strip()
    )
