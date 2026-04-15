import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from app.core.config import Settings


TEST_CASE_STRATEGY_COLUMNS = {
    "requested_strategy": "TEXT NOT NULL DEFAULT 'interaction_first'",
    "effective_strategy": "TEXT NOT NULL DEFAULT 'interaction_first'",
}
EXECUTION_STRATEGY_COLUMNS = {
    "requested_strategy": "TEXT NOT NULL DEFAULT 'interaction_first'",
    "effective_strategy": "TEXT NOT NULL DEFAULT 'interaction_first'",
    "fallback_reason": "TEXT",
    "site_profile": "TEXT",
}
SELF_HEAL_STRATEGY_COLUMNS = {
    "strategy_before": "TEXT NOT NULL DEFAULT 'interaction_first'",
    "strategy_after": "TEXT NOT NULL DEFAULT 'interaction_first'",
    "fallback_reason": "TEXT",
    "site_profile": "TEXT",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_runtime_directories(settings: Settings) -> None:
    settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
    settings.executions_dir.mkdir(parents=True, exist_ok=True)
    settings.knowledge_base_dir.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection(settings: Settings) -> Iterator[sqlite3.Connection]:
    ensure_runtime_directories(settings)
    connection = sqlite3.connect(settings.sqlite_db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database(settings: Settings) -> None:
    ensure_runtime_directories(settings)
    with get_connection(settings) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS test_case (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                generated_code TEXT NOT NULL,
                raw_output TEXT NOT NULL,
                rag_context TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                requested_strategy TEXT NOT NULL DEFAULT 'interaction_first',
                effective_strategy TEXT NOT NULL DEFAULT 'interaction_first'
            );

            CREATE TABLE IF NOT EXISTS execution_record (
                id TEXT PRIMARY KEY,
                test_case_id TEXT NOT NULL,
                executed_code TEXT NOT NULL,
                status TEXT NOT NULL,
                run_directory TEXT,
                script_path TEXT,
                logs TEXT,
                error TEXT,
                validation_errors TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                requested_strategy TEXT NOT NULL DEFAULT 'interaction_first',
                effective_strategy TEXT NOT NULL DEFAULT 'interaction_first',
                fallback_reason TEXT,
                site_profile TEXT,
                FOREIGN KEY(test_case_id) REFERENCES test_case(id)
            );

            CREATE TABLE IF NOT EXISTS self_heal_attempt (
                id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                failure_reason TEXT,
                repair_summary TEXT,
                original_code TEXT NOT NULL,
                repaired_code TEXT,
                logs TEXT,
                error TEXT,
                validation_errors TEXT NOT NULL,
                run_directory TEXT,
                script_path TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                strategy_before TEXT NOT NULL DEFAULT 'interaction_first',
                strategy_after TEXT NOT NULL DEFAULT 'interaction_first',
                fallback_reason TEXT,
                site_profile TEXT,
                FOREIGN KEY(execution_id) REFERENCES execution_record(id)
            );

            CREATE TABLE IF NOT EXISTS system_setting (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        _ensure_columns(connection, "test_case", TEST_CASE_STRATEGY_COLUMNS)
        _ensure_columns(connection, "execution_record", EXECUTION_STRATEGY_COLUMNS)
        _ensure_columns(connection, "self_heal_attempt", SELF_HEAL_STRATEGY_COLUMNS)


def _ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    expected_columns: dict[str, str],
) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_definition in expected_columns.items():
        if column_name in existing_columns:
            continue
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )
