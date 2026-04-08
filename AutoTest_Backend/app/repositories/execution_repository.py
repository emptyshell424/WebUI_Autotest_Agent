import json
import uuid

from app.core.config import Settings
from app.core.database import get_connection, utc_now_iso
from app.models import ExecutionRecord, SelfHealAttemptRecord


class ExecutionRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, *, test_case_id: str, executed_code: str) -> ExecutionRecord:
        record = ExecutionRecord(
            id=str(uuid.uuid4()),
            test_case_id=test_case_id,
            executed_code=executed_code,
            status="queued",
            run_directory=None,
            script_path=None,
            logs=None,
            error=None,
            validation_errors=[],
            created_at=utc_now_iso(),
            started_at=None,
            finished_at=None,
        )
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                INSERT INTO execution_record (
                    id, test_case_id, executed_code, status, run_directory, script_path,
                    logs, error, validation_errors, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.test_case_id,
                    record.executed_code,
                    record.status,
                    record.run_directory,
                    record.script_path,
                    record.logs,
                    record.error,
                    json.dumps(record.validation_errors),
                    record.created_at,
                    record.started_at,
                    record.finished_at,
                ),
            )
        return record

    def get(self, execution_id: str) -> ExecutionRecord | None:
        with get_connection(self.settings) as connection:
            row = connection.execute(
                """
                SELECT
                    e.id,
                    e.test_case_id,
                    e.executed_code,
                    e.status,
                    e.run_directory,
                    e.script_path,
                    e.logs,
                    e.error,
                    e.validation_errors,
                    e.created_at,
                    e.started_at,
                    e.finished_at,
                    t.title AS test_case_title,
                    COALESCE(stats.self_heal_count, 0) AS self_heal_count
                FROM execution_record AS e
                JOIN test_case AS t ON t.id = e.test_case_id
                LEFT JOIN (
                    SELECT execution_id, COUNT(*) AS self_heal_count
                    FROM self_heal_attempt
                    GROUP BY execution_id
                ) AS stats ON stats.execution_id = e.id
                WHERE e.id = ?
                """,
                (execution_id,),
            ).fetchone()
        record = self._from_row(row)
        if record is None:
            return None
        record.self_heal_attempts = self.list_self_heal_attempts(execution_id)
        record.self_heal_count = len(record.self_heal_attempts)
        record.self_heal_triggered = record.self_heal_count > 0
        record.healed = record.status == "healed_completed"
        return record

    def list_recent(self, *, limit: int = 20, offset: int = 0) -> list[ExecutionRecord]:
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT
                    e.id,
                    e.test_case_id,
                    e.executed_code,
                    e.status,
                    e.run_directory,
                    e.script_path,
                    e.logs,
                    e.error,
                    e.validation_errors,
                    e.created_at,
                    e.started_at,
                    e.finished_at,
                    t.title AS test_case_title,
                    COALESCE(stats.self_heal_count, 0) AS self_heal_count
                FROM execution_record AS e
                JOIN test_case AS t ON t.id = e.test_case_id
                LEFT JOIN (
                    SELECT execution_id, COUNT(*) AS self_heal_count
                    FROM self_heal_attempt
                    GROUP BY execution_id
                ) AS stats ON stats.execution_id = e.id
                ORDER BY e.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [record for row in rows if (record := self._from_row(row)) is not None]

    def mark_running(
        self,
        execution_id: str,
        *,
        run_directory: str,
        script_path: str,
    ) -> None:
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                UPDATE execution_record
                SET status = ?, run_directory = ?, script_path = ?, started_at = ?
                WHERE id = ?
                """,
                ("running", run_directory, script_path, utc_now_iso(), execution_id),
            )

    def mark_finished(
        self,
        execution_id: str,
        *,
        status: str,
        logs: str | None = None,
        error: str | None = None,
        validation_errors: list[str] | None = None,
        run_directory: str | None = None,
        script_path: str | None = None,
    ) -> None:
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                UPDATE execution_record
                SET status = ?,
                    logs = ?,
                    error = ?,
                    validation_errors = ?,
                    run_directory = COALESCE(?, run_directory),
                    script_path = COALESCE(?, script_path),
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    logs,
                    error,
                    json.dumps(validation_errors or []),
                    run_directory,
                    script_path,
                    utc_now_iso(),
                    execution_id,
                ),
            )

    def create_self_heal_attempt(
        self,
        *,
        execution_id: str,
        attempt_number: int,
        failure_reason: str | None,
        repair_summary: str | None,
        original_code: str,
    ) -> SelfHealAttemptRecord:
        record = SelfHealAttemptRecord(
            id=str(uuid.uuid4()),
            execution_id=execution_id,
            attempt_number=attempt_number,
            status="queued",
            failure_reason=failure_reason,
            repair_summary=repair_summary,
            original_code=original_code,
            repaired_code=None,
            logs=None,
            error=None,
            validation_errors=[],
            run_directory=None,
            script_path=None,
            created_at=utc_now_iso(),
            started_at=None,
            finished_at=None,
        )
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                INSERT INTO self_heal_attempt (
                    id, execution_id, attempt_number, status, failure_reason, repair_summary,
                    original_code, repaired_code, logs, error, validation_errors, run_directory,
                    script_path, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.execution_id,
                    record.attempt_number,
                    record.status,
                    record.failure_reason,
                    record.repair_summary,
                    record.original_code,
                    record.repaired_code,
                    record.logs,
                    record.error,
                    json.dumps(record.validation_errors),
                    record.run_directory,
                    record.script_path,
                    record.created_at,
                    record.started_at,
                    record.finished_at,
                ),
            )
        return record

    def mark_self_heal_attempt_running(
        self,
        attempt_id: str,
        *,
        repaired_code: str,
        repair_summary: str | None,
        run_directory: str,
        script_path: str,
    ) -> None:
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                UPDATE self_heal_attempt
                SET status = ?,
                    repaired_code = ?,
                    repair_summary = ?,
                    run_directory = ?,
                    script_path = ?,
                    started_at = ?
                WHERE id = ?
                """,
                (
                    "running",
                    repaired_code,
                    repair_summary,
                    run_directory,
                    script_path,
                    utc_now_iso(),
                    attempt_id,
                ),
            )

    def mark_self_heal_attempt_finished(
        self,
        attempt_id: str,
        *,
        status: str,
        repaired_code: str | None = None,
        repair_summary: str | None = None,
        logs: str | None = None,
        error: str | None = None,
        validation_errors: list[str] | None = None,
        run_directory: str | None = None,
        script_path: str | None = None,
    ) -> None:
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                UPDATE self_heal_attempt
                SET status = ?,
                    repaired_code = COALESCE(?, repaired_code),
                    repair_summary = COALESCE(?, repair_summary),
                    logs = ?,
                    error = ?,
                    validation_errors = ?,
                    run_directory = COALESCE(?, run_directory),
                    script_path = COALESCE(?, script_path),
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    repaired_code,
                    repair_summary,
                    logs,
                    error,
                    json.dumps(validation_errors or []),
                    run_directory,
                    script_path,
                    utc_now_iso(),
                    attempt_id,
                ),
            )

    def list_self_heal_attempts(self, execution_id: str) -> list[SelfHealAttemptRecord]:
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    execution_id,
                    attempt_number,
                    status,
                    failure_reason,
                    repair_summary,
                    original_code,
                    repaired_code,
                    logs,
                    error,
                    validation_errors,
                    run_directory,
                    script_path,
                    created_at,
                    started_at,
                    finished_at
                FROM self_heal_attempt
                WHERE execution_id = ?
                ORDER BY attempt_number ASC
                """,
                (execution_id,),
            ).fetchall()
        return [self._attempt_from_row(row) for row in rows]

    def get_stats(self) -> dict[str, int | float]:
        with get_connection(self.settings) as connection:
            generated_count = connection.execute("SELECT COUNT(*) FROM test_case").fetchone()[0]
            execution_count = connection.execute("SELECT COUNT(*) FROM execution_record").fetchone()[0]
            effective_execution_count = connection.execute(
                "SELECT COUNT(*) FROM execution_record WHERE status != 'blocked'"
            ).fetchone()[0]
            first_pass_success_count = connection.execute(
                "SELECT COUNT(*) FROM execution_record WHERE status = 'completed'"
            ).fetchone()[0]
            self_heal_triggered_count = connection.execute(
                "SELECT COUNT(DISTINCT execution_id) FROM self_heal_attempt"
            ).fetchone()[0]
            self_heal_success_count = connection.execute(
                "SELECT COUNT(*) FROM execution_record WHERE status = 'healed_completed'"
            ).fetchone()[0]
        final_success_count = first_pass_success_count + self_heal_success_count
        return {
            "generated_count": generated_count,
            "execution_count": execution_count,
            "effective_execution_count": effective_execution_count,
            "first_pass_success_count": first_pass_success_count,
            "self_heal_triggered_count": self_heal_triggered_count,
            "self_heal_success_count": self_heal_success_count,
            "final_success_count": final_success_count,
            "first_pass_success_rate": self._safe_rate(
                first_pass_success_count, effective_execution_count
            ),
            "self_heal_triggered_rate": self._safe_rate(
                self_heal_triggered_count, effective_execution_count
            ),
            "self_heal_success_rate": self._safe_rate(
                self_heal_success_count, self_heal_triggered_count
            ),
            "final_success_rate": self._safe_rate(final_success_count, effective_execution_count),
        }

    def _from_row(self, row) -> ExecutionRecord | None:
        if row is None:
            return None
        payload = dict(row)
        payload["validation_errors"] = json.loads(payload.get("validation_errors") or "[]")
        payload["self_heal_count"] = int(payload.get("self_heal_count") or 0)
        payload["self_heal_triggered"] = payload["self_heal_count"] > 0
        payload["healed"] = payload.get("status") == "healed_completed"
        payload["self_heal_attempts"] = []
        return ExecutionRecord(**payload)

    def _attempt_from_row(self, row) -> SelfHealAttemptRecord:
        payload = dict(row)
        payload["validation_errors"] = json.loads(payload.get("validation_errors") or "[]")
        return SelfHealAttemptRecord(**payload)

    def _safe_rate(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator, 4)
