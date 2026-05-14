"""Tool: validate generated code for safety before execution."""

from __future__ import annotations

from typing import Any

from app.services.execution_service import validate_generated_code
from app.tools.base import BaseTool, ToolResult


class ValidateCodeTool(BaseTool):
    """Runs the safety-validation checks on a code snippet."""

    @property
    def name(self) -> str:
        return "validate_code"

    @property
    def description(self) -> str:
        return (
            "Check a Python Selenium script for unsafe imports or blocked calls. "
            "Returns a list of validation errors (empty means the code is safe)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to validate.",
                },
            },
            "required": ["code"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        code: str = kwargs["code"]
        try:
            errors = validate_generated_code(code)
            if errors:
                return ToolResult(
                    success=True,
                    data={"validation_errors": errors, "safe": False},
                    summary=f"Validation found {len(errors)} issue(s): {'; '.join(errors[:3])}",
                )
            return ToolResult(
                success=True,
                data={"validation_errors": [], "safe": True},
                summary="Code passed safety validation.",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
