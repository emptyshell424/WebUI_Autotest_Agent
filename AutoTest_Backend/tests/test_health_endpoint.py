import unittest
from pathlib import Path
import shutil

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


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


if __name__ == "__main__":
    unittest.main()
