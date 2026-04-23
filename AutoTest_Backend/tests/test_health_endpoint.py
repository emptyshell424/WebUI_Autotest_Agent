import unittest

from . import _bootstrap
from .runtime_support import RuntimeWorkspaceTestCase
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import initialize_database
from app.main import create_app
from app.repositories import TestCaseRepository
from app.services.strategy_service import StrategyService


class HealthEndpointTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        self.temp_dir = self.create_temp_dir("health-endpoint")
        root = self.temp_dir
        (root / "docs" / "knowledge").mkdir(parents=True, exist_ok=True)
        (root / "docs" / "knowledge" / "demo.md").write_text(
            "Use explicit waits before clicking.",
            encoding="utf-8",
        )
        self.settings = Settings(
            DEEPSEEK_API_KEY=None,
            SQLITE_DB_PATH=str(root / "data" / "app.db"),
            VECTOR_STORE_DIR=str(root / "data" / "rag"),
            KNOWLEDGE_BASE_DIR=str(root / "docs" / "knowledge"),
            EXECUTIONS_DIR=str(root / "runs"),
        )
        initialize_database(self.settings)
        self.client = TestClient(create_app(self.settings))

    def test_health_endpoint_reports_degraded_without_model(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["model"]["status"], "degraded")
        self.assertEqual(payload["knowledge_base"]["details"]["document_count"], 1)

    def test_knowledge_rebuild_indexes_documents(self) -> None:
        response = self.client.post("/api/v1/knowledge/rebuild")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["document_count"], 1)
        self.assertGreaterEqual(payload["chunk_count"], 1)

    def test_test_case_endpoint_returns_saved_case(self) -> None:
        prompt = "Open Baidu, search for DeepSeek, then wait for the results page."
        strategy = StrategyService().analyze_generation(prompt)
        record = TestCaseRepository(self.settings).create(
            title="baidu search",
            prompt=prompt,
            generated_code="print('Test Completed')",
            raw_output="print('Test Completed')",
            rag_context="Use explicit waits.",
            requested_strategy=strategy.requested_strategy,
            effective_strategy=strategy.effective_strategy,
        )

        response = self.client.get(f"/api/v1/test-cases/{record.id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], record.id)
        self.assertEqual(payload["prompt"], prompt)
        self.assertEqual(payload["requested_strategy"], strategy.requested_strategy)
        self.assertEqual(payload["effective_strategy"], strategy.effective_strategy)

    def test_execution_list_supports_status_filter_and_total(self) -> None:
        strategy = StrategyService().analyze_generation("Open Baidu and print completion.")
        repository = TestCaseRepository(self.settings)
        record = repository.create(
            title="status-filter",
            prompt="Open Baidu and print completion.",
            generated_code="print('Test Completed')",
            raw_output="print('Test Completed')",
            rag_context="Use explicit waits.",
            requested_strategy=strategy.requested_strategy,
            effective_strategy=strategy.effective_strategy,
        )
        from app.repositories import ExecutionRepository

        execution_repository = ExecutionRepository(self.settings)
        execution = execution_repository.create(
            test_case_id=record.id,
            executed_code=record.generated_code,
            requested_strategy=strategy.requested_strategy,
            effective_strategy=strategy.effective_strategy,
            site_profile=None,
        )
        execution_repository.mark_running(
            execution.id,
            run_directory="runs/status-filter",
            script_path="runs/status-filter/generated_test.py",
        )
        execution_repository.mark_finished(execution.id, status="failed", error="boom")

        filtered = self.client.get("/api/v1/executions", params={"status": "failed", "limit": 10, "offset": 0})
        self.assertEqual(filtered.status_code, 200)
        payload = filtered.json()
        self.assertEqual(payload["status_filter"], "failed")
        self.assertGreaterEqual(payload["total"], 1)


if __name__ == "__main__":
    unittest.main()
