import json
import uuid

from app.core.config import Settings
from app.core.database import get_connection, utc_now_iso
from app.core.exceptions import AppError
from app.models import ExecutionRecord, ExecutionTrendPoint, SelfHealAttemptRecord

TERMINAL_EXECUTION_STATUSES = (
    'completed',
    'failed',
    'healed_completed',
    'healed_failed',
    'cancelled',
)
SELF_HEAL_TERMINAL_STATUSES = ('healed_completed', 'healed_failed')

VALID_EXECUTION_TRANSITIONS: dict[str, set[str]] = {
    'queued': {'running', 'failed', 'cancelled'},
    'running': {'completed', 'failed', 'blocked', 'healed_completed', 'healed_failed', 'cancelled'},
    'blocked': set(),
    'completed': set(),
    'failed': set(),
    'healed_completed': set(),
    'healed_failed': set(),
    'cancelled': set(),
}

VALID_HEAL_ATTEMPT_TRANSITIONS: dict[str, set[str]] = {
    'queued': {'running', 'blocked', 'repair_failed'},
    'running': {'completed', 'failed', 'blocked'},
    'blocked': set(),
    'completed': set(),
    'failed': set(),
    'repair_failed': set(),
}


def _check_execution_transition(connection, execution_id: str, target_status: str) -> None:
    row = connection.execute(
        "SELECT status FROM execution_record WHERE id = ?",
        (execution_id,),
    ).fetchone()
    if row is None:
        raise AppError(
            "Execution record was not found.",
            status_code=404,
            code="execution_not_found",
        )
    current = row[0]
    allowed = VALID_EXECUTION_TRANSITIONS.get(current, set())
    if target_status not in allowed:
        raise AppError(
            f"Invalid status transition from '{current}' to '{target_status}'.",
            status_code=409,
            code="invalid_status_transition",
        )


def _check_attempt_transition(connection, attempt_id: str, target_status: str) -> None:
    row = connection.execute(
        "SELECT status FROM self_heal_attempt WHERE id = ?",
        (attempt_id,),
    ).fetchone()
    if row is None:
        raise AppError(
            "Self-heal attempt record was not found.",
            status_code=404,
            code="attempt_not_found",
        )
    current = row[0]
    allowed = VALID_HEAL_ATTEMPT_TRANSITIONS.get(current, set())
    if target_status not in allowed:
        raise AppError(
            f"Invalid attempt status transition from '{current}' to '{target_status}'.",
            status_code=409,
            code="invalid_status_transition",
        )


class ExecutionRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(
        self,
        *,
        test_case_id: str,
        executed_code: str,
        requested_strategy: str,
        effective_strategy: str,
        fallback_reason: str | None = None,
        site_profile: str | None = None,
    ) -> ExecutionRecord:
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
            requested_strategy=requested_strategy,
            effective_strategy=effective_strategy,
            fallback_reason=fallback_reason,
            site_profile=site_profile,
        )
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                INSERT INTO execution_record (
                    id, test_case_id, executed_code, status, run_directory, script_path,
                    logs, error, validation_errors, created_at, started_at, finished_at,
                    requested_strategy, effective_strategy, fallback_reason, site_profile
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    record.requested_strategy,
                    record.effective_strategy,
                    record.fallback_reason,
                    record.site_profile,
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
                    e.requested_strategy,
                    e.effective_strategy,
                    e.fallback_reason,
                    e.site_profile,
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
                    e.requested_strategy,
                    e.effective_strategy,
                    e.fallback_reason,
                    e.site_profile,
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

    def list_recent_filtered(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ) -> list[ExecutionRecord]:
        with get_connection(self.settings) as connection:
            where_clause = "WHERE e.status = ?" if status else ""
            params: tuple[object, ...] = (status, limit, offset) if status else (limit, offset)
            rows = connection.execute(
                f"""
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
                    e.requested_strategy,
                    e.effective_strategy,
                    e.fallback_reason,
                    e.site_profile,
                    t.title AS test_case_title,
                    COALESCE(stats.self_heal_count, 0) AS self_heal_count
                FROM execution_record AS e
                JOIN test_case AS t ON t.id = e.test_case_id
                LEFT JOIN (
                    SELECT execution_id, COUNT(*) AS self_heal_count
                    FROM self_heal_attempt
                    GROUP BY execution_id
                ) AS stats ON stats.execution_id = e.id
                {where_clause}
                ORDER BY e.created_at DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [record for row in rows if (record := self._from_row(row)) is not None]

    def count_recent(self, *, status: str | None = None) -> int:
        with get_connection(self.settings) as connection:
            if status:
                return int(
                    connection.execute(
                        "SELECT COUNT(*) FROM execution_record WHERE status = ?",
                        (status,),
                    ).fetchone()[0]
                )
            return int(connection.execute("SELECT COUNT(*) FROM execution_record").fetchone()[0])

    def mark_running(
        self,
        execution_id: str,
        *,
        run_directory: str,
        script_path: str,
    ) -> None:
        with get_connection(self.settings) as connection:
            _check_execution_transition(connection, execution_id, "running")
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
        effective_strategy: str | None = None,
        fallback_reason: str | None = None,
        site_profile: str | None = None,
    ) -> None:
        with get_connection(self.settings) as connection:
            _check_execution_transition(connection, execution_id, status)
            connection.execute(
                """
                UPDATE execution_record
                SET status = ?,
                    logs = ?,
                    error = ?,
                    validation_errors = ?,
                    run_directory = COALESCE(?, run_directory),
                    script_path = COALESCE(?, script_path),
                    effective_strategy = COALESCE(?, effective_strategy),
                    fallback_reason = COALESCE(?, fallback_reason),
                    site_profile = COALESCE(?, site_profile),
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
                    effective_strategy,
                    fallback_reason,
                    site_profile,
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
        strategy_before: str,
        strategy_after: str,
        fallback_reason: str | None,
        site_profile: str | None,
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
            strategy_before=strategy_before,
            strategy_after=strategy_after,
            fallback_reason=fallback_reason,
            site_profile=site_profile,
        )
        with get_connection(self.settings) as connection:
            connection.execute(
                """
                INSERT INTO self_heal_attempt (
                    id, execution_id, attempt_number, status, failure_reason, repair_summary,
                    original_code, repaired_code, logs, error, validation_errors, run_directory,
                    script_path, created_at, started_at, finished_at,
                    strategy_before, strategy_after, fallback_reason, site_profile
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    record.strategy_before,
                    record.strategy_after,
                    record.fallback_reason,
                    record.site_profile,
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
            _check_attempt_transition(connection, attempt_id, "running")
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
            _check_attempt_transition(connection, attempt_id, status)
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
                    finished_at,
                    strategy_before,
                    strategy_after,
                    fallback_reason,
                    site_profile
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
                """
                SELECT COUNT(*)
                FROM execution_record
                WHERE status IN (?, ?, ?, ?, ?)
                """,
                TERMINAL_EXECUTION_STATUSES,
            ).fetchone()[0]
            first_pass_success_count = connection.execute(
                "SELECT COUNT(*) FROM execution_record WHERE status = 'completed'"
            ).fetchone()[0]
            self_heal_triggered_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM execution_record
                WHERE status IN (?, ?)
                """,
                SELF_HEAL_TERMINAL_STATUSES,
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
            "trend": [self._trend_to_dict(point) for point in self.list_trend()],
        }

    def list_trend(self, *, limit: int = 7) -> list[ExecutionTrendPoint]:
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT
                    substr(created_at, 1, 10) AS bucket,
                    COUNT(*) AS execution_count,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
                    SUM(CASE WHEN status = 'healed_completed' THEN 1 ELSE 0 END) AS healed_completed_count,
                    SUM(CASE WHEN status IN ('failed', 'healed_failed') THEN 1 ELSE 0 END) AS failed_count,
                    SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked_count
                FROM execution_record
                GROUP BY substr(created_at, 1, 10)
                ORDER BY bucket DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        points: list[ExecutionTrendPoint] = []
        for row in reversed(rows):
            execution_count = int(row["execution_count"] or 0)
            completed_count = int(row["completed_count"] or 0)
            healed_completed_count = int(row["healed_completed_count"] or 0)
            points.append(
                ExecutionTrendPoint(
                    bucket=row["bucket"],
                    execution_count=execution_count,
                    completed_count=completed_count,
                    healed_completed_count=healed_completed_count,
                    failed_count=int(row["failed_count"] or 0),
                    blocked_count=int(row["blocked_count"] or 0),
                    final_success_rate=self._safe_rate(
                        completed_count + healed_completed_count,
                        execution_count,
                    ),
                )
            )
        return points

    def count_active(self) -> int:
        with get_connection(self.settings) as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM execution_record WHERE status IN ('queued', 'running')"
                ).fetchone()[0]
            )

    def recover_interrupted_executions(self) -> int:
        interrupted_error = "Execution interrupted before completion. Service likely restarted."
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                "SELECT id FROM execution_record WHERE status IN ('queued', 'running')"
            ).fetchall()
            execution_ids = [row["id"] for row in rows]
            if not execution_ids:
                return 0
            timestamp = utc_now_iso()
            for execution_id in execution_ids:
                connection.execute(
                    """
                    UPDATE execution_record
                    SET status = 'failed',
                        error = COALESCE(error, ?),
                        finished_at = COALESCE(finished_at, ?)
                    WHERE id = ?
                    """,
                    (interrupted_error, timestamp, execution_id),
                )
            return len(execution_ids)

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

    def _trend_to_dict(self, point: ExecutionTrendPoint) -> dict[str, int | float | str]:
        return {
            "bucket": point.bucket,
            "execution_count": point.execution_count,
            "completed_count": point.completed_count,
            "healed_completed_count": point.healed_completed_count,
            "failed_count": point.failed_count,
            "blocked_count": point.blocked_count,
            "final_success_rate": point.final_success_rate,
        }

