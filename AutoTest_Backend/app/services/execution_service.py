import ast
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import AppError
from app.repositories import ExecutionRepository, TestCaseRepository
from app.services.llm_service import LLMService
from app.utils.code_parser import clean_code


SAFE_IMPORTS = {
    "datetime",
    "json",
    "math",
    "random",
    "re",
    "selenium",
    "time",
}
BLOCKED_CALLS = {"breakpoint", "compile", "eval", "exec", "input", "open", "__import__"}
BLOCKED_PREFIXES = ("os.", "pathlib.", "shutil.", "socket.", "subprocess.", "sys.")


def validate_generated_code(code: str) -> list[str]:
    errors: list[str] = []
    if not code.strip():
        return ["Generated code is empty."]

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"Syntax error: {exc.msg} (line {exc.lineno})"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in SAFE_IMPORTS:
                    errors.append(f"Import '{alias.name}' is not allowed.")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module not in SAFE_IMPORTS:
                errors.append(f"Import from '{node.module}' is not allowed.")
        elif isinstance(node, ast.Call):
            name = _resolve_callable_name(node.func)
            if name in BLOCKED_CALLS or name.startswith(BLOCKED_PREFIXES):
                errors.append(f"Call '{name}' is not allowed.")
    return sorted(set(errors))


def _resolve_callable_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _resolve_callable_name(node.value)
        if prefix:
            return f"{prefix}.{node.attr}"
        return node.attr
    return ""


@dataclass(slots=True)
class ScriptRunResult:
    status: str
    logs: str
    error: str | None
    validation_errors: list[str]
    run_directory: str
    script_path: str
    executed_code: str


class ExecutionService:
    def __init__(
        self,
        settings: Settings,
        execution_repository: ExecutionRepository,
        test_case_repository: TestCaseRepository,
        llm_service: LLMService,
    ) -> None:
        self.settings = settings
        self.execution_repository = execution_repository
        self.test_case_repository = test_case_repository
        self.llm_service = llm_service

    def create_execution(self, *, test_case_id: str, code_override: str | None = None):
        test_case = self.test_case_repository.get(test_case_id)
        if test_case is None:
            raise AppError(
                "Test case was not found.",
                status_code=404,
                code="test_case_not_found",
            )

        executed_code = (code_override or test_case.generated_code).strip()
        record = self.execution_repository.create(
            test_case_id=test_case_id,
            executed_code=executed_code,
        )
        self.test_case_repository.update_status(test_case_id, "queued")

        worker = threading.Thread(
            target=self._run_execution,
            args=(record.id,),
            daemon=True,
        )
        worker.start()
        return self.execution_repository.get(record.id)

    def get_execution(self, execution_id: str):
        record = self.execution_repository.get(execution_id)
        if record is None:
            raise AppError(
                "Execution record was not found.",
                status_code=404,
                code="execution_not_found",
            )
        return record

    def list_executions(self, *, limit: int, offset: int):
        return self.execution_repository.list_recent(limit=limit, offset=offset)

    def get_stats(self):
        return self.execution_repository.get_stats()

    def _run_execution(self, execution_id: str) -> None:
        record = self.execution_repository.get(execution_id)
        if record is None:
            return
        test_case = self.test_case_repository.get(record.test_case_id)
        if test_case is None:
            return

        primary_result = self._execute_script(
            code=record.executed_code,
            run_directory=self.settings.executions_dir / execution_id / "initial",
            status_callback=lambda run_dir, script_path: self.execution_repository.mark_running(
                execution_id,
                run_directory=str(run_dir),
                script_path=str(script_path),
            ),
        )

        if primary_result.status == "blocked":
            self.execution_repository.mark_finished(
                execution_id,
                status="blocked",
                logs=primary_result.logs,
                error=primary_result.error,
                validation_errors=primary_result.validation_errors,
                run_directory=primary_result.run_directory,
                script_path=primary_result.script_path,
            )
            self.test_case_repository.update_status(record.test_case_id, "blocked")
            return

        if primary_result.status == "completed":
            self.execution_repository.mark_finished(
                execution_id,
                status="completed",
                logs=primary_result.logs,
                error=primary_result.error,
                run_directory=primary_result.run_directory,
                script_path=primary_result.script_path,
            )
            self.test_case_repository.update_status(record.test_case_id, "completed")
            return

        final_status = self._try_self_heal(
            execution_id=execution_id,
            prompt=test_case.prompt,
            rag_context=test_case.rag_context,
            original_code=record.executed_code,
            primary_result=primary_result,
        )
        self.test_case_repository.update_status(record.test_case_id, final_status)

    def _try_self_heal(
        self,
        *,
        execution_id: str,
        prompt: str,
        rag_context: str,
        original_code: str,
        primary_result: ScriptRunResult,
    ) -> str:
        if self.settings.MAX_SELF_HEAL_ATTEMPTS <= 0:
            self.execution_repository.mark_finished(
                execution_id,
                status="failed",
                logs=primary_result.logs,
                error=primary_result.error,
                run_directory=primary_result.run_directory,
                script_path=primary_result.script_path,
            )
            return "failed"

        repair_summary = self._build_repair_summary(primary_result.error, primary_result.logs)
        attempt = self.execution_repository.create_self_heal_attempt(
            execution_id=execution_id,
            attempt_number=1,
            failure_reason=primary_result.error or primary_result.logs,
            repair_summary=repair_summary,
            original_code=original_code,
        )

        try:
            repaired_code = clean_code(
                self.llm_service.repair_script(
                    prompt=prompt,
                    original_code=original_code,
                    error=primary_result.error or "",
                    logs=primary_result.logs,
                    context=rag_context,
                )
            ).strip()
        except AppError as exc:
            self.execution_repository.mark_self_heal_attempt_finished(
                attempt.id,
                status="repair_failed",
                repair_summary=repair_summary,
                logs=primary_result.logs,
                error=exc.message,
            )
            self.execution_repository.mark_finished(
                execution_id,
                status="healed_failed",
                logs=primary_result.logs,
                error=primary_result.error or exc.message,
                run_directory=primary_result.run_directory,
                script_path=primary_result.script_path,
            )
            return "healed_failed"

        repair_run_dir = self.settings.executions_dir / execution_id / "repair-1"
        repair_script_path = repair_run_dir / "generated_test.py"
        self.execution_repository.mark_self_heal_attempt_running(
            attempt.id,
            repaired_code=repaired_code,
            repair_summary=repair_summary,
            run_directory=str(repair_run_dir),
            script_path=str(repair_script_path),
        )

        repair_result = self._execute_script(
            code=repaired_code,
            run_directory=repair_run_dir,
            status_callback=None,
        )
        self.execution_repository.mark_self_heal_attempt_finished(
            attempt.id,
            status=repair_result.status,
            repaired_code=repaired_code,
            repair_summary=repair_summary,
            logs=repair_result.logs,
            error=repair_result.error,
            validation_errors=repair_result.validation_errors,
            run_directory=repair_result.run_directory,
            script_path=repair_result.script_path,
        )

        final_status = "healed_completed" if repair_result.status == "completed" else "healed_failed"
        self.execution_repository.mark_finished(
            execution_id,
            status=final_status,
            logs=repair_result.logs,
            error=repair_result.error,
            validation_errors=repair_result.validation_errors,
            run_directory=repair_result.run_directory,
            script_path=repair_result.script_path,
        )
        return final_status

    def _execute_script(
        self,
        *,
        code: str,
        run_directory: Path,
        status_callback,
    ) -> ScriptRunResult:
        validation_errors = validate_generated_code(code)
        run_directory.mkdir(parents=True, exist_ok=True)
        script_path = run_directory / "generated_test.py"

        if validation_errors:
            return ScriptRunResult(
                status="blocked",
                logs="",
                error="Execution blocked by safety validation.",
                validation_errors=validation_errors,
                run_directory=str(run_directory),
                script_path=str(script_path),
                executed_code=code,
            )

        script_path.write_text(code, encoding="utf-8")
        if status_callback is not None:
            status_callback(run_directory, script_path)

        stdout_path = run_directory / "stdout.log"
        stderr_path = run_directory / "stderr.log"
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr_handle:
                result = subprocess.run(
                    [sys.executable, script_path.name],
                    cwd=run_directory,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    text=True,
                    encoding="utf-8",
                    timeout=self.settings.EXECUTION_TIMEOUT_SECONDS,
                    creationflags=creationflags,
                    env=env,
                )
        except subprocess.TimeoutExpired:
            return ScriptRunResult(
                status="failed",
                logs=self._read_text(stdout_path),
                error="Execution timed out.",
                validation_errors=[],
                run_directory=str(run_directory),
                script_path=str(script_path),
                executed_code=code,
            )
        except Exception as exc:
            return ScriptRunResult(
                status="failed",
                logs=self._read_text(stdout_path),
                error=f"Execution crashed: {exc}",
                validation_errors=[],
                run_directory=str(run_directory),
                script_path=str(script_path),
                executed_code=code,
            )

        logs = self._read_text(stdout_path)
        error = self._read_text(stderr_path) or None
        status = "completed" if result.returncode == 0 else "failed"
        return ScriptRunResult(
            status=status,
            logs=logs,
            error=error,
            validation_errors=[],
            run_directory=str(run_directory),
            script_path=str(script_path),
            executed_code=code,
        )

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def _build_repair_summary(self, error: str | None, logs: str | None) -> str:
        combined = f"{error or ''}\n{logs or ''}".lower()
        if "timeout" in combined:
            return "Adjusted waits and readiness checks after a timeout-related failure."
        if "no such element" in combined:
            return "Retried with stronger element anchors after a missing-element failure."
        if "iframe" in combined or "frame" in combined:
            return "Retried with frame-aware Selenium interactions."
        return "Retried with a repaired Selenium script based on the recorded runtime failure."
