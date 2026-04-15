import sqlite3
import shutil
import unittest
from pathlib import Path

from . import _bootstrap

from app.core.config import Settings
from app.core.database import initialize_database


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / "_migration_runtime"
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_dir / "app.db"
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            CREATE TABLE test_case (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                generated_code TEXT NOT NULL,
                raw_output TEXT NOT NULL,
                rag_context TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE execution_record (
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
                finished_at TEXT
            );

            CREATE TABLE self_heal_attempt (
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
                finished_at TEXT
            );
            """
        )
        connection.commit()
        connection.close()

        self.settings = Settings(
            DEEPSEEK_API_KEY=None,
            SQLITE_DB_PATH=str(self.db_path),
            VECTOR_STORE_DIR=str(self.temp_dir / "rag"),
            KNOWLEDGE_BASE_DIR=str(self.temp_dir / "knowledge"),
            EXECUTIONS_DIR=str(self.temp_dir / "runs"),
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialize_database_adds_strategy_columns_to_existing_tables(self) -> None:
        initialize_database(self.settings)

        connection = sqlite3.connect(self.db_path)
        try:
            test_case_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(test_case)").fetchall()
            }
            execution_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(execution_record)").fetchall()
            }
            self_heal_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(self_heal_attempt)").fetchall()
            }
        finally:
            connection.close()

        self.assertIn("requested_strategy", test_case_columns)
        self.assertIn("effective_strategy", test_case_columns)
        self.assertIn("requested_strategy", execution_columns)
        self.assertIn("effective_strategy", execution_columns)
        self.assertIn("fallback_reason", execution_columns)
        self.assertIn("site_profile", execution_columns)
        self.assertIn("strategy_before", self_heal_columns)
        self.assertIn("strategy_after", self_heal_columns)
        self.assertIn("fallback_reason", self_heal_columns)
        self.assertIn("site_profile", self_heal_columns)


if __name__ == "__main__":
    unittest.main()
