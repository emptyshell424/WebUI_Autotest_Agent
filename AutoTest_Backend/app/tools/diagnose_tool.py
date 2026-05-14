"""Tool: diagnose why a script execution failed."""

from __future__ import annotations

from typing import Any

from app.services.failure_diagnostic_service import FailureDiagnosticService
from app.services.intelligent_diagnostic_service import IntelligentDiagnosticService
from app.tools.base import BaseTool, ToolResult


class DiagnoseFailureTool(BaseTool):
    """Wraps diagnostic services as an agent-callable tool.

    Uses IntelligentDiagnosticService (LLM-powered) when an LLM is provided,
    otherwise falls back to the legacy regex-based FailureDiagnosticService.
    """

    def __init__(
        self,
        diagnostic_service: FailureDiagnosticService | None = None,
        llm_service=None,
    ) -> None:
        self._legacy = diagnostic_service or FailureDiagnosticService()
        self._intelligent = IntelligentDiagnosticService(
            llm_service=llm_service,
            legacy_service=self._legacy,
        )

    @property
    def name(self) -> str:
        return "diagnose_failure"

    @property
    def description(self) -> str:
        return (
            "Analyse the error, logs, and optional validation errors from a failed "
            "script execution. Returns a structured diagnosis including failure type, "
            "suspected root cause, and repair hint."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "error": {
                    "type": "string",
                    "description": "Stderr or exception text from the failed execution.",
                },
                "logs": {
                    "type": "string",
                    "description": "Stdout logs from the failed execution.",
                },
                "code": {
                    "type": "string",
                    "description": "The failed Python script source (optional, improves diagnosis).",
                },
                "validation_errors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Safety-validation error list (if any).",
                },
            },
            "required": [],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        error: str | None = kwargs.get("error")
        logs: str | None = kwargs.get("logs")
        code: str | None = kwargs.get("code")
        validation_errors: list[str] | None = kwargs.get("validation_errors")
        try:
            diagnosis = self._intelligent.diagnose(
                error=error,
                logs=logs,
                code=code,
                validation_errors=validation_errors,
            )
            return ToolResult(
                success=True,
                data={
                    "failure_type": diagnosis.failure_type,
                    "failure_signal": diagnosis.failure_signal,
                    "root_cause_analysis": diagnosis.root_cause_analysis,
                    "repair_strategy": diagnosis.repair_strategy,
                    "confidence": diagnosis.confidence,
                    "suggested_selectors": diagnosis.suggested_selectors,
                    "source": diagnosis.source,
                    # Backward-compatible aliases
                    "suspected_root_cause": diagnosis.root_cause_analysis,
                    "repair_hint": diagnosis.repair_strategy,
                },
                summary=(
                    f"Diagnosis ({diagnosis.source}): {diagnosis.failure_type} — "
                    f"{diagnosis.root_cause_analysis[:120]}"
                ),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
