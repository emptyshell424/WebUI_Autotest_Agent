"""Tool: execute a Selenium test script and return results."""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool, ToolResult


class ExecuteScriptTool(BaseTool):
    """Wraps ExecutionService.create_execution as an agent-callable tool."""

    def __init__(self, execution_service) -> None:
        self._execution_service = execution_service

    @property
    def name(self) -> str:
        return "execute_script"

    @property
    def description(self) -> str:
        return (
            "Execute a previously generated Selenium test script by its test case ID. "
            "Optionally provide a code_override to run modified code instead of the "
            "original. Returns execution ID and initial status."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_case_id": {
                    "type": "string",
                    "description": "ID of the test case whose script should be executed.",
                },
                "code_override": {
                    "type": "string",
                    "description": "Optional replacement code to execute instead of the stored script.",
                },
            },
            "required": ["test_case_id"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        test_case_id: str = kwargs["test_case_id"]
        code_override: str | None = kwargs.get("code_override")
        try:
            record = self._execution_service.create_execution(
                test_case_id=test_case_id,
                code_override=code_override,
            )
            return ToolResult(
                success=True,
                data={
                    "execution_id": record.id,
                    "status": record.status,
                    "test_case_id": record.test_case_id,
                },
                summary=f"Execution {record.id} created with status '{record.status}'.",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))


class GetExecutionResultTool(BaseTool):
    """Poll execution status and retrieve final results."""

    def __init__(self, execution_service) -> None:
        self._execution_service = execution_service

    @property
    def name(self) -> str:
        return "get_execution_result"

    @property
    def description(self) -> str:
        return (
            "Get the current status and results of an execution by its ID. "
            "Use this to check whether an execution has completed, failed, or "
            "is still running."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "execution_id": {
                    "type": "string",
                    "description": "ID of the execution to query.",
                },
            },
            "required": ["execution_id"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        execution_id: str = kwargs["execution_id"]
        try:
            record = self._execution_service.get_execution(execution_id)
            data: dict[str, Any] = {
                "execution_id": record.id,
                "status": record.status,
                "logs": record.logs,
                "error": record.error,
                "self_heal_triggered": record.self_heal_triggered,
                "self_heal_count": record.self_heal_count,
                "healed": record.healed,
            }
            if record.status in ("completed", "healed_completed"):
                summary = f"Execution {record.id} succeeded (status={record.status})."
            elif record.status in ("failed", "healed_failed", "blocked"):
                error_brief = (record.error or "")[:200]
                summary = f"Execution {record.id} {record.status}: {error_brief}"
            else:
                summary = f"Execution {record.id} is still {record.status}."
            return ToolResult(success=True, data=data, summary=summary)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
