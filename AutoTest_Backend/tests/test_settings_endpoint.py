import unittest

from . import _bootstrap
from .runtime_support import RuntimeWorkspaceTestCase
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class SettingsEndpointTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        self.temp_dir = self.create_temp_dir("settings-endpoint")
        self.settings = Settings(
            DEEPSEEK_API_KEY=None,
            SQLITE_DB_PATH=str(self.temp_dir / "data" / "app.db"),
            VECTOR_STORE_DIR=str(self.temp_dir / "data" / "rag"),
            KNOWLEDGE_BASE_DIR=str(self.temp_dir / "docs" / "knowledge"),
            EXECUTIONS_DIR=str(self.temp_dir / "runs"),
            EXECUTION_TIMEOUT_SECONDS=60,
            MAX_SELF_HEAL_ATTEMPTS=1,
            MAX_CONCURRENT_EXECUTIONS=1,
        )
        self.client = TestClient(create_app(self.settings))

    def test_settings_endpoint_reads_and_updates_runtime_values(self) -> None:
        response = self.client.get("/api/v1/settings")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["settings"]["execution_timeout_seconds"], 60)
        self.assertEqual(payload["settings"]["max_self_heal_attempts"], 1)
        self.assertEqual(payload["settings"]["max_concurrent_executions"], 1)
        self.assertNotIn("knowledge_base_dir", payload["settings"])
        self.assertNotIn("model_name", payload["settings"])

        update_response = self.client.put(
            "/api/v1/settings",
            json={
                "execution_timeout_seconds": 90,
                "max_self_heal_attempts": 2,
                "max_concurrent_executions": 3,
            },
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["settings"]["execution_timeout_seconds"], 90)
        self.assertEqual(updated["settings"]["max_self_heal_attempts"], 2)
        self.assertEqual(updated["settings"]["max_concurrent_executions"], 3)
        self.assertNotIn("knowledge_base_dir", updated["settings"])
        self.assertNotIn("model_name", updated["settings"])
        self.assertTrue(any(item["key"] == "max_concurrent_executions" for item in updated["items"]))


if __name__ == "__main__":
    unittest.main()
