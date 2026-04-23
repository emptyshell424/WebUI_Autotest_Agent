import ast
import logging
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
from app.services.strategy_service import StrategyService
from app.utils.code_parser import clean_code

logger = logging.getLogger("autotest.execution")


class _CancelToken:
    """Thread-safe cancellation signal for a single execution."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


SAFE_IMPORTS = {
    "datetime",
    "json",
    "math",
    "random",
    "re",
    "selenium",
    "time",
    "urllib",
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
        strategy_service: StrategyService,
    ) -> None:
        self.settings = settings
        self.execution_repository = execution_repository
        self.test_case_repository = test_case_repository
        self.llm_service = llm_service
        self.strategy_service = strategy_service
        self._cancel_tokens: dict[str, _CancelToken] = {}

    def create_execution(self, *, test_case_id: str, code_override: str | None = None):
        if self.execution_repository.count_active() >= self.settings.MAX_CONCURRENT_EXECUTIONS:
            raise AppError(
                "Execution queue is full. Wait for active jobs to finish before starting another run.",
                status_code=409,
                code="execution_queue_full",
            )
        test_case = self.test_case_repository.get(test_case_id)
        if test_case is None:
            raise AppError(
                "Test case was not found.",
                status_code=404,
                code="test_case_not_found",
            )

        strategy_context = self.strategy_service.analyze_generation(test_case.prompt)
        executed_code = (code_override or test_case.generated_code).strip()
        if not executed_code:
            raise AppError(
                'Execution code is empty.',
                status_code=422,
                code='empty_execution_code',
            )
        record = self.execution_repository.create(
            test_case_id=test_case_id,
            executed_code=executed_code,
            requested_strategy=test_case.requested_strategy,
            effective_strategy=test_case.effective_strategy,
            site_profile=strategy_context.site_profile,
        )
        self.test_case_repository.update_status(test_case_id, "queued")

        cancel_token = _CancelToken()
        self._cancel_tokens[record.id] = cancel_token

        worker = threading.Thread(
            target=self._run_execution,
            args=(record.id, cancel_token),
            daemon=True,
        )
        worker.start()
        return self.execution_repository.get(record.id)

    def cancel_execution(self, execution_id: str):
        record = self.execution_repository.get(execution_id)
        if record is None:
            raise AppError(
                "Execution record was not found.",
                status_code=404,
                code="execution_not_found",
            )
        if record.status not in ("queued", "running"):
            raise AppError(
                "Only queued or running executions can be cancelled.",
                status_code=409,
                code="cancel_not_allowed",
            )
        token = self._cancel_tokens.get(execution_id)
        if token is not None:
            token.cancel()
        self.execution_repository.mark_finished(
            execution_id,
            status="cancelled",
            error="Execution cancelled by user.",
        )
        self._cancel_tokens.pop(execution_id, None)
        return self.execution_repository.get(execution_id)

    def get_execution(self, execution_id: str):
        record = self.execution_repository.get(execution_id)
        if record is None:
            raise AppError(
                "Execution record was not found.",
                status_code=404,
                code="execution_not_found",
            )
        return record

    def list_executions(self, *, limit: int, offset: int, status: str | None = None):
        return self.execution_repository.list_recent_filtered(limit=limit, offset=offset, status=status)

    def count_executions(self, *, status: str | None = None) -> int:
        return self.execution_repository.count_recent(status=status)

    def get_stats(self):
        return self.execution_repository.get_stats()

    def _run_execution(self, execution_id: str, cancel_token: _CancelToken) -> None:
        record = self.execution_repository.get(execution_id)
        if record is None:
            return
        test_case = self.test_case_repository.get(record.test_case_id)
        if test_case is None:
            return

        try:
            self._run_execution_inner(execution_id, record, test_case, cancel_token)
        except Exception as exc:
            logger.exception("Unexpected error during execution %s", execution_id)
            try:
                self.execution_repository.mark_finished(
                    execution_id,
                    status="failed",
                    error=f"Unexpected error during execution: {exc}",
                )
                self.test_case_repository.update_status(record.test_case_id, "failed")
            except Exception:
                logger.exception("Failed to mark execution %s as failed", execution_id)
        finally:
            self._cancel_tokens.pop(execution_id, None)

    def _run_execution_inner(
        self,
        execution_id: str,
        record,
        test_case,
        cancel_token: _CancelToken,
    ) -> None:
        if cancel_token.is_cancelled:
            return

        primary_result = self._execute_script(
            code=record.executed_code,
            run_directory=self.settings.executions_dir / execution_id / "initial",
            status_callback=lambda run_dir, script_path: self.execution_repository.mark_running(
                execution_id,
                run_directory=str(run_dir),
                script_path=str(script_path),
            ),
            cancel_token=cancel_token,
        )

        if cancel_token.is_cancelled:
            return

        if primary_result.status == "blocked":
            self.execution_repository.mark_finished(
                execution_id,
                status="blocked",
                logs=primary_result.logs,
                error=primary_result.error,
                validation_errors=primary_result.validation_errors,
                run_directory=primary_result.run_directory,
                script_path=primary_result.script_path,
                effective_strategy=record.effective_strategy,
                site_profile=record.site_profile,
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
                effective_strategy=record.effective_strategy,
                site_profile=record.site_profile,
            )
            self.test_case_repository.update_status(record.test_case_id, "completed")
            return

        final_status = self._try_self_heal(
            execution_id=execution_id,
            prompt=test_case.prompt,
            rag_context=test_case.rag_context,
            original_code=record.executed_code,
            primary_result=primary_result,
            requested_strategy=record.requested_strategy,
            effective_strategy=record.effective_strategy,
            site_profile=record.site_profile,
            cancel_token=cancel_token,
        )
        if final_status is not None:
            self.test_case_repository.update_status(record.test_case_id, final_status)

    def _try_self_heal(
        self,
        *,
        execution_id: str,
        prompt: str,
        rag_context: str,
        original_code: str,
        primary_result: ScriptRunResult,
        requested_strategy: str,
        effective_strategy: str,
        site_profile: str | None,
        cancel_token: _CancelToken | None = None,
    ) -> str | None:
        if self.settings.MAX_SELF_HEAL_ATTEMPTS <= 0:
            self.execution_repository.mark_finished(
                execution_id,
                status="failed",
                logs=primary_result.logs,
                error=primary_result.error,
                run_directory=primary_result.run_directory,
                script_path=primary_result.script_path,
                effective_strategy=effective_strategy,
                site_profile=site_profile,
            )
            return "failed"

        current_code = original_code
        current_result = primary_result
        current_strategy = effective_strategy
        current_fallback_reason: str | None = None
        current_site_profile = site_profile

        for attempt_number in range(1, self.settings.MAX_SELF_HEAL_ATTEMPTS + 1):
            if cancel_token.is_cancelled:
                return None

            strategy_decision = self.strategy_service.analyze_repair(
                prompt=prompt,
                error=current_result.error,
                original_code=current_code,
                requested_strategy=requested_strategy,
                effective_strategy=current_strategy,
                site_profile=current_site_profile,
            )
            repair_summary = self.strategy_service.build_repair_summary(
                strategy_decision
            ) or self._build_generic_repair_summary(
                current_result.error,
                current_result.logs,
            )
            repair_guidance = self.strategy_service.build_repair_guidance(strategy_decision)
            attempt = self.execution_repository.create_self_heal_attempt(
                execution_id=execution_id,
                attempt_number=attempt_number,
                failure_reason=current_result.error or current_result.logs,
                repair_summary=repair_summary,
                original_code=current_code,
                strategy_before=strategy_decision.strategy_before,
                strategy_after=strategy_decision.strategy_after,
                fallback_reason=strategy_decision.fallback_reason,
                site_profile=strategy_decision.site_profile,
            )

            try:
                repaired_code = clean_code(
                    self.llm_service.repair_script(
                        prompt=prompt,
                        original_code=current_code,
                        error=current_result.error or "",
                        logs=current_result.logs,
                        context=rag_context,
                        strategy_decision=strategy_decision,
                        repair_guidance=repair_guidance,
                    )
                ).strip()
            except AppError as exc:
                self.execution_repository.mark_self_heal_attempt_finished(
                    attempt.id,
                    status="repair_failed",
                    repair_summary=repair_summary,
                    logs=current_result.logs,
                    error=exc.message,
                )
                if attempt_number == self.settings.MAX_SELF_HEAL_ATTEMPTS:
                    self.execution_repository.mark_finished(
                        execution_id,
                        status="healed_failed",
                        logs=current_result.logs,
                        error=exc.message,
                        validation_errors=current_result.validation_errors,
                        run_directory=current_result.run_directory,
                        script_path=current_result.script_path,
                        effective_strategy=current_strategy,
                        fallback_reason=current_fallback_reason,
                        site_profile=current_site_profile,
                    )
                    return "healed_failed"
                continue

            if not repaired_code:
                repair_error = "Repair returned empty code after cleanup."
                self.execution_repository.mark_self_heal_attempt_finished(
                    attempt.id,
                    status="repair_failed",
                    repair_summary=repair_summary,
                    logs=current_result.logs,
                    error=repair_error,
                )
                if attempt_number == self.settings.MAX_SELF_HEAL_ATTEMPTS:
                    self.execution_repository.mark_finished(
                        execution_id,
                        status="healed_failed",
                        logs=current_result.logs,
                        error=repair_error,
                        validation_errors=current_result.validation_errors,
                        run_directory=current_result.run_directory,
                        script_path=current_result.script_path,
                        effective_strategy=current_strategy,
                        fallback_reason=current_fallback_reason,
                        site_profile=current_site_profile,
                    )
                    return "healed_failed"
                continue

            repair_run_dir = self.settings.executions_dir / execution_id / f"repair-{attempt_number}"
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
                cancel_token=cancel_token,
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

            current_code = repaired_code
            current_result = repair_result
            current_strategy = strategy_decision.strategy_after
            current_fallback_reason = strategy_decision.fallback_reason
            current_site_profile = strategy_decision.site_profile

            if repair_result.status == "completed":
                self.execution_repository.mark_finished(
                    execution_id,
                    status="healed_completed",
                    logs=repair_result.logs,
                    error=repair_result.error,
                    validation_errors=repair_result.validation_errors,
                    run_directory=repair_result.run_directory,
                    script_path=repair_result.script_path,
                    effective_strategy=current_strategy,
                    fallback_reason=current_fallback_reason,
                    site_profile=current_site_profile,
                )
                return "healed_completed"

        self.execution_repository.mark_finished(
            execution_id,
            status="healed_failed",
            logs=current_result.logs,
            error=current_result.error,
            validation_errors=current_result.validation_errors,
            run_directory=current_result.run_directory,
            script_path=current_result.script_path,
            effective_strategy=current_strategy,
            fallback_reason=current_fallback_reason,
            site_profile=current_site_profile,
        )
        return "healed_failed"

    def _execute_script(
        self,
        *,
        code: str,
        run_directory: Path,
        status_callback,
        cancel_token: _CancelToken | None = None,
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
                proc = subprocess.Popen(
                    [sys.executable, script_path.name],
                    cwd=run_directory,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    text=True,
                    encoding="utf-8",
                    creationflags=creationflags,
                    env=env,
                )
                try:
                    proc.wait(timeout=self.settings.EXECUTION_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    raise
                if cancel_token is not None and cancel_token.is_cancelled:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    return ScriptRunResult(
                        status="failed",
                        logs=self._read_text(stdout_path),
                        error="Execution cancelled by user.",
                        validation_errors=[],
                        run_directory=str(run_directory),
                        script_path=str(script_path),
                        executed_code=code,
                    )
                result = proc
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

    def _build_generic_repair_summary(
        self,
        error: str | None,
        logs: str | None,
    ) -> str:
        combined = f"{error or ''}\n{logs or ''}".lower()
        if "timeout" in combined:
            return "Adjusted waits and readiness checks after a timeout-related failure."
        if "no such element" in combined:
            return "Retried with stronger element anchors after a missing-element failure."
        if "iframe" in combined or "frame" in combined:
            return "Retried with frame-aware Selenium interactions."
        return "Retried with a repaired Selenium script based on the recorded runtime failure."

