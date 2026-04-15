import shutil
import unittest
from pathlib import Path

from . import _bootstrap
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import initialize_database
from app.main import create_app
from app.repositories import TestCaseRepository
from app.services.strategy_service import StrategyService


class HealthEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(__file__).resolve().parent / "_runtime"
        shutil.rmtree(self.temp_dir, ignore_errors=True)
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

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

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


if __name__ == "__main__":
    unittest.main()
