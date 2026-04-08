import shutil
import unittest
from pathlib import Path

import tests._bootstrap
from app.core.config import Settings
from app.core.database import initialize_database
from app.repositories import ExecutionRepository, TestCaseRepository
from app.services.execution_service import ExecutionService


class FakeLLMService:
    def __init__(self, repaired_code: str) -> None:
        self.repaired_code = repaired_code

    def repair_script(self, **_: str) -> str:
        return self.repaired_code


class SelfHealFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / "_self_heal_runtime"
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        (self.temp_dir / "docs" / "knowledge").mkdir(parents=True, exist_ok=True)
        self.settings = Settings(
            DEEPSEEK_API_KEY="test-key",
            SQLITE_DB_PATH=str(self.temp_dir / "data" / "app.db"),
            VECTOR_STORE_DIR=str(self.temp_dir / "data" / "rag"),
            KNOWLEDGE_BASE_DIR=str(self.temp_dir / "docs" / "knowledge"),
            EXECUTIONS_DIR=str(self.temp_dir / "runs"),
            EXECUTION_TIMEOUT_SECONDS=5,
            MAX_SELF_HEAL_ATTEMPTS=1,
        )
        initialize_database(self.settings)
        self.test_cases = TestCaseRepository(self.settings)
        self.executions = ExecutionRepository(self.settings)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_failed_execution_can_be_repaired(self) -> None:
        case = self.test_cases.create(
            title="repair me",
            prompt="Open page and verify success message",
            generated_code="raise RuntimeError('boom')",
            raw_output="raise RuntimeError('boom')",
            rag_context="Use robust waits and assertions.",
        )
        record = self.executions.create(test_case_id=case.id, executed_code=case.generated_code)
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            FakeLLMService("print('Test Completed')"),
        )

        service._run_execution(record.id)

        saved = self.executions.get(record.id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "healed_completed")
        self.assertTrue(saved.self_heal_triggered)
        self.assertEqual(saved.self_heal_count, 1)
        self.assertEqual(saved.self_heal_attempts[0].status, "completed")
        self.assertIn("Test Completed", saved.logs or "")

    def test_self_heal_still_respects_safety_validation(self) -> None:
        case = self.test_cases.create(
            title="blocked repair",
            prompt="Open page and verify success message",
            generated_code="raise RuntimeError('boom')",
            raw_output="raise RuntimeError('boom')",
            rag_context="Avoid unsafe imports.",
        )
        record = self.executions.create(test_case_id=case.id, executed_code=case.generated_code)
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            FakeLLMService("import os\nprint('unsafe')"),
        )

        service._run_execution(record.id)

        saved = self.executions.get(record.id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "healed_failed")
        self.assertEqual(saved.self_heal_attempts[0].status, "blocked")
        self.assertTrue(saved.self_heal_attempts[0].validation_errors)

    def test_stats_include_self_heal_metrics(self) -> None:
        completed_case = self.test_cases.create(
            title="completed",
            prompt="done",
            generated_code="print('done')",
            raw_output="print('done')",
            rag_context="",
        )
        completed_execution = self.executions.create(
            test_case_id=completed_case.id,
            executed_code=completed_case.generated_code,
        )
        self.executions.mark_finished(
            completed_execution.id,
            status="completed",
            logs="done",
            error=None,
        )

        healed_case = self.test_cases.create(
            title="healed",
            prompt="healed",
            generated_code="raise RuntimeError('boom')",
            raw_output="raise RuntimeError('boom')",
            rag_context="",
        )
        healed_execution = self.executions.create(
            test_case_id=healed_case.id,
            executed_code=healed_case.generated_code,
        )
        self.executions.create_self_heal_attempt(
            execution_id=healed_execution.id,
            attempt_number=1,
            failure_reason="boom",
            repair_summary="patched selectors",
            original_code=healed_case.generated_code,
        )
        self.executions.mark_finished(
            healed_execution.id,
            status="healed_completed",
            logs="Test Completed",
            error=None,
        )

        blocked_case = self.test_cases.create(
            title="blocked",
            prompt="blocked",
            generated_code="import os",
            raw_output="import os",
            rag_context="",
        )
        blocked_execution = self.executions.create(
            test_case_id=blocked_case.id,
            executed_code=blocked_case.generated_code,
        )
        self.executions.mark_finished(
            blocked_execution.id,
            status="blocked",
            logs="",
            error="Execution blocked by safety validation.",
            validation_errors=["Import 'os' is not allowed."],
        )

        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            FakeLLMService("print('unused')"),
        )
        stats = service.get_stats()

        self.assertEqual(stats["generated_count"], 3)
        self.assertEqual(stats["execution_count"], 3)
        self.assertEqual(stats["effective_execution_count"], 2)
        self.assertEqual(stats["first_pass_success_count"], 1)
        self.assertEqual(stats["self_heal_triggered_count"], 1)
        self.assertEqual(stats["self_heal_success_count"], 1)
        self.assertEqual(stats["final_success_count"], 2)
        self.assertEqual(stats["final_success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()

