import unittest

from . import _bootstrap
from .runtime_support import RuntimeWorkspaceTestCase
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.database import initialize_database
from app.core.container import create_container
from app.repositories import ExecutionRepository, TestCaseRepository
from app.services.execution_service import ExecutionService, _CancelToken
from app.services.strategy_service import StrategyService


class FakeLLMService:
    def __init__(self, repaired_code: str) -> None:
        self.repaired_code = repaired_code
        self.last_kwargs: dict[str, object] = {}

    def repair_script(self, **kwargs: object) -> str:
        self.last_kwargs = kwargs
        return self.repaired_code


class SequenceLLMService:
    def __init__(self, repaired_codes: list[str]) -> None:
        self.repaired_codes = repaired_codes
        self.last_kwargs: dict[str, object] = {}
        self.call_count = 0

    def repair_script(self, **kwargs: object) -> str:
        self.last_kwargs = kwargs
        result = self.repaired_codes[self.call_count]
        self.call_count += 1
        return result


class SelfHealFlowTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        self.temp_dir = self.create_temp_dir("self-heal-flow")
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
        self.strategy_service = StrategyService()

    def _create_case(self, *, title: str, prompt: str, generated_code: str, rag_context: str):
        strategy = self.strategy_service.analyze_generation(prompt)
        return self.test_cases.create(
            title=title,
            prompt=prompt,
            generated_code=generated_code,
            raw_output=generated_code,
            rag_context=rag_context,
            requested_strategy=strategy.requested_strategy,
            effective_strategy=strategy.effective_strategy,
        )

    def test_failed_execution_can_be_repaired_without_strategy_downgrade(self) -> None:
        case = self._create_case(
            title="repair me",
            prompt="Open page and verify success message",
            generated_code="raise RuntimeError('boom')",
            rag_context="Use robust waits and assertions.",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        llm = FakeLLMService("print('Test Completed')")
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            llm,
            self.strategy_service,
        )

        service._run_execution(record.id, _CancelToken())

        saved = self.executions.get(record.id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "healed_completed")
        self.assertTrue(saved.self_heal_triggered)
        self.assertEqual(saved.self_heal_count, 1)
        self.assertEqual(saved.self_heal_attempts[0].status, "completed")
        self.assertIn("Test Completed", saved.logs or "")
        self.assertEqual(saved.effective_strategy, "interaction_first")
        self.assertEqual(saved.self_heal_attempts[0].strategy_before, "interaction_first")
        self.assertEqual(saved.self_heal_attempts[0].strategy_after, "interaction_first")
        self.assertEqual(llm.last_kwargs.get("repair_guidance"), "")

    def test_self_heal_switches_baidu_homepage_timeout_to_results_page_flow(self) -> None:
        original_code = (
            "from selenium.common.exceptions import TimeoutException\n"
            "homepage_url = 'https://www.baidu.com'\n"
            "search_anchor = 'kw'\n"
            "raise TimeoutException('Timed out waiting for homepage search input kw')\n"
        )
        repaired_code = (
            "from urllib.parse import quote_plus\n"
            "url = f'https://www.baidu.com/s?wd={quote_plus(\"DeepSeek\")}'\n"
            "assert 'baidu.com/s?wd=' in url\n"
            "print('Test Completed')\n"
        )
        case = self._create_case(
            title="baidu search",
            prompt="Open Baidu, search for DeepSeek, wait for the results page, then print test completed.",
            generated_code=original_code,
            rag_context="Baidu search validation keeps homepage interaction by default and may downgrade during self-heal.",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile="baidu_search",
        )
        llm = FakeLLMService(repaired_code)
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            llm,
            self.strategy_service,
        )

        service._run_execution(record.id, _CancelToken())

        saved = self.executions.get(record.id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "healed_completed")
        self.assertEqual(saved.effective_strategy, "result_first")
        self.assertEqual(saved.fallback_reason, "baidu_homepage_search_anchor_timeout")
        self.assertEqual(saved.site_profile, "baidu_search")
        self.assertEqual(saved.self_heal_attempts[0].status, "completed")
        self.assertEqual(saved.self_heal_attempts[0].strategy_before, "interaction_first")
        self.assertEqual(saved.self_heal_attempts[0].strategy_after, "result_first")
        self.assertEqual(
            saved.self_heal_attempts[0].fallback_reason,
            "baidu_homepage_search_anchor_timeout",
        )
        self.assertIn("homepage search input flow", saved.self_heal_attempts[0].repair_summary or "")
        self.assertIn("direct Baidu results page", saved.self_heal_attempts[0].repair_summary or "")
        self.assertIn("baidu.com/s?wd=", saved.self_heal_attempts[0].repaired_code or "")
        self.assertIn("quote_plus", llm.last_kwargs.get("repair_guidance", ""))
        self.assertIn("interaction_first to result_first", llm.last_kwargs.get("repair_guidance", ""))
        self.assertEqual(llm.last_kwargs["strategy_decision"].strategy_after, "result_first")

    def test_self_heal_still_respects_safety_validation(self) -> None:
        case = self._create_case(
            title="blocked repair",
            prompt="Open page and verify success message",
            generated_code="raise RuntimeError('boom')",
            rag_context="Avoid unsafe imports.",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            FakeLLMService("import os\nprint('unsafe')"),
            self.strategy_service,
        )

        service._run_execution(record.id, _CancelToken())

        saved = self.executions.get(record.id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "healed_failed")
        self.assertEqual(saved.self_heal_attempts[0].status, "blocked")
        self.assertTrue(saved.self_heal_attempts[0].validation_errors)

    def test_self_heal_retries_until_the_configured_attempt_limit(self) -> None:
        self.settings.MAX_SELF_HEAL_ATTEMPTS = 2
        case = self._create_case(
            title="retry twice",
            prompt="Open page and verify success message",
            generated_code="raise RuntimeError('boom')",
            rag_context="Use stable selectors.",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        llm = SequenceLLMService(
            [
                "raise RuntimeError('still broken')",
                "print('Test Completed')",
            ]
        )
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            llm,
            self.strategy_service,
        )

        service._run_execution(record.id, _CancelToken())

        saved = self.executions.get(record.id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "healed_completed")
        self.assertEqual(saved.self_heal_count, 2)
        self.assertEqual(saved.self_heal_attempts[0].status, "failed")
        self.assertEqual(saved.self_heal_attempts[1].status, "completed")
        self.assertEqual(llm.call_count, 2)

    def test_stats_include_self_heal_metrics(self) -> None:
        completed_case = self._create_case(
            title="completed",
            prompt="done",
            generated_code="print('done')",
            rag_context="",
        )
        completed_execution = self.executions.create(
            test_case_id=completed_case.id,
            executed_code=completed_case.generated_code,
            requested_strategy=completed_case.requested_strategy,
            effective_strategy=completed_case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_running(
            completed_execution.id,
            run_directory="runs/completed",
            script_path="runs/completed/generated_test.py",
        )
        self.executions.mark_finished(
            completed_execution.id,
            status="completed",
            logs="done",
            error=None,
        )

        healed_case = self._create_case(
            title="healed",
            prompt="healed",
            generated_code="raise RuntimeError('boom')",
            rag_context="",
        )
        healed_execution = self.executions.create(
            test_case_id=healed_case.id,
            executed_code=healed_case.generated_code,
            requested_strategy=healed_case.requested_strategy,
            effective_strategy=healed_case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_running(
            healed_execution.id,
            run_directory="runs/healed",
            script_path="runs/healed/generated_test.py",
        )
        self.executions.create_self_heal_attempt(
            execution_id=healed_execution.id,
            attempt_number=1,
            failure_reason="boom",
            repair_summary="patched selectors",
            original_code=healed_case.generated_code,
            strategy_before="interaction_first",
            strategy_after="interaction_first",
            fallback_reason=None,
            site_profile=None,
        )
        self.executions.mark_finished(
            healed_execution.id,
            status="healed_completed",
            logs="Test Completed",
            error=None,
        )

        blocked_case = self._create_case(
            title="blocked",
            prompt="blocked",
            generated_code="import os",
            rag_context="",
        )
        blocked_execution = self.executions.create(
            test_case_id=blocked_case.id,
            executed_code=blocked_case.generated_code,
            requested_strategy=blocked_case.requested_strategy,
            effective_strategy=blocked_case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_running(
            blocked_execution.id,
            run_directory="runs/blocked",
            script_path="runs/blocked/generated_test.py",
        )
        self.executions.mark_finished(
            blocked_execution.id,
            status="blocked",
            logs="",
            error="Execution blocked by safety validation.",
            validation_errors=["Import 'os' is not allowed."],
        )

        queued_case = self._create_case(
            title="queued",
            prompt="queued",
            generated_code="print('queued')",
            rag_context="",
        )
        self.executions.create(
            test_case_id=queued_case.id,
            executed_code=queued_case.generated_code,
            requested_strategy=queued_case.requested_strategy,
            effective_strategy=queued_case.effective_strategy,
            site_profile=None,
        )

        running_case = self._create_case(
            title="running",
            prompt="running",
            generated_code="print('running')",
            rag_context="",
        )
        running_execution = self.executions.create(
            test_case_id=running_case.id,
            executed_code=running_case.generated_code,
            requested_strategy=running_case.requested_strategy,
            effective_strategy=running_case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_running(
            running_execution.id,
            run_directory="runs/in-progress",
            script_path="runs/in-progress/generated_test.py",
        )

        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            FakeLLMService("print('unused')"),
            self.strategy_service,
        )
        stats = service.get_stats()

        self.assertEqual(stats["generated_count"], 5)
        self.assertEqual(stats["execution_count"], 5)
        self.assertEqual(stats["effective_execution_count"], 2)
        self.assertEqual(stats["first_pass_success_count"], 1)
        self.assertEqual(stats["self_heal_triggered_count"], 1)
        self.assertEqual(stats["self_heal_success_count"], 1)
        self.assertEqual(stats["final_success_count"], 2)
        self.assertEqual(stats["final_success_rate"], 1.0)
        self.assertTrue(stats["trend"])

    def test_queue_limit_rejects_new_execution_when_active_count_is_full(self) -> None:
        self.settings.MAX_CONCURRENT_EXECUTIONS = 1
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            FakeLLMService("print('unused')"),
            self.strategy_service,
        )
        case = self._create_case(
            title="queue limit",
            prompt="queued",
            generated_code="print('queued')",
            rag_context="",
        )
        active = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_running(
            active.id,
            run_directory="runs/in-progress",
            script_path="runs/in-progress/generated_test.py",
        )

        with self.assertRaises(AppError) as context:
            service.create_execution(test_case_id=case.id)

        self.assertEqual(context.exception.code, "execution_queue_full")

    def test_cancel_execution_marks_queued_as_cancelled(self) -> None:
        case = self._create_case(
            title="cancel me queued",
            prompt="Open page and verify success message",
            generated_code="print('hello')",
            rag_context="",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            FakeLLMService("print('unused')"),
            self.strategy_service,
        )
        result = service.cancel_execution(record.id)
        self.assertEqual(result.status, "cancelled")
        self.assertIn("cancelled", result.error or "")

    def test_cancel_execution_marks_running_as_cancelled(self) -> None:
        case = self._create_case(
            title="cancel me running",
            prompt="Open page and verify success message",
            generated_code="print('hello')",
            rag_context="",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_running(
            record.id,
            run_directory="runs/cancel-running",
            script_path="runs/cancel-running/generated_test.py",
        )
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            FakeLLMService("print('unused')"),
            self.strategy_service,
        )
        result = service.cancel_execution(record.id)
        self.assertEqual(result.status, "cancelled")
        self.assertIn("cancelled", result.error or "")

    def test_cancel_execution_rejects_already_finished(self) -> None:
        case = self._create_case(
            title="already done",
            prompt="done",
            generated_code="print('done')",
            rag_context="",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_running(
            record.id,
            run_directory="runs/already-done",
            script_path="runs/already-done/generated_test.py",
        )
        self.executions.mark_finished(record.id, status="completed", logs="done")
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            FakeLLMService("print('unused')"),
            self.strategy_service,
        )

        with self.assertRaises(AppError) as context:
            service.cancel_execution(record.id)
        self.assertEqual(context.exception.code, "cancel_not_allowed")

    def test_service_recovers_interrupted_active_records_on_startup(self) -> None:
        case = self._create_case(
            title="interrupted",
            prompt="queued",
            generated_code="print('queued')",
            rag_context="",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_running(
            record.id,
            run_directory="runs/in-progress",
            script_path="runs/in-progress/generated_test.py",
        )

        container = create_container(self.settings)
        self.assertIsNotNone(container.execution_service)

        recovered = self.executions.get(record.id)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.status, "failed")
        self.assertIn("interrupted", recovered.error or "")


    def test_invalid_transition_from_queued_to_completed_is_rejected(self) -> None:
        case = self._create_case(
            title="bad transition",
            prompt="done",
            generated_code="print('done')",
            rag_context="",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        with self.assertRaises(AppError) as context:
            self.executions.mark_finished(record.id, status="completed", logs="done")
        self.assertEqual(context.exception.code, "invalid_status_transition")

    def test_invalid_transition_from_completed_to_running_is_rejected(self) -> None:
        case = self._create_case(
            title="double run",
            prompt="done",
            generated_code="print('done')",
            rag_context="",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_running(
            record.id,
            run_directory="runs/done",
            script_path="runs/done/generated_test.py",
        )
        self.executions.mark_finished(record.id, status="completed", logs="done")
        with self.assertRaises(AppError) as context:
            self.executions.mark_running(
                record.id,
                run_directory="runs/again",
                script_path="runs/again/generated_test.py",
            )
        self.assertEqual(context.exception.code, "invalid_status_transition")

    def test_unexpected_exception_is_persisted_as_failed(self) -> None:
        case = self._create_case(
            title="crash",
            prompt="Open page",
            generated_code="print('crash')",
            rag_context="",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        llm = FakeLLMService("print('unused')")
        service = ExecutionService(
            self.settings,
            self.executions,
            self.test_cases,
            llm,
            self.strategy_service,
        )
        original_execute = service._execute_script
        def exploding_execute(**kwargs):
            raise RuntimeError("disk full")
        service._execute_script = exploding_execute

        service._run_execution(record.id, _CancelToken())

        saved = self.executions.get(record.id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "failed")
        self.assertIn("disk full", saved.error or "")

    def test_valid_transition_queued_to_cancelled(self) -> None:
        case = self._create_case(
            title="cancel queued",
            prompt="cancel",
            generated_code="print('cancel')",
            rag_context="",
        )
        record = self.executions.create(
            test_case_id=case.id,
            executed_code=case.generated_code,
            requested_strategy=case.requested_strategy,
            effective_strategy=case.effective_strategy,
            site_profile=None,
        )
        self.executions.mark_finished(record.id, status="cancelled", error="User cancelled.")
        saved = self.executions.get(record.id)
        self.assertEqual(saved.status, "cancelled")


if __name__ == "__main__":
    unittest.main()
