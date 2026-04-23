"""Integration tests covering the core API chain using FastAPI TestClient.

Covers: POST /generate → POST /executions → GET /executions/{id}
        → GET /executions → GET /executions/stats → DELETE /executions/{id}
"""

import unittest

from . import _bootstrap
from .runtime_support import RuntimeWorkspaceTestCase

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import initialize_database
from app.main import create_app
from app.repositories import ExecutionRepository, TestCaseRepository
from app.services.strategy_service import StrategyService


class APIIntegrationTests(RuntimeWorkspaceTestCase):
    """End-to-end API integration tests with a real SQLite database."""

    def setUp(self) -> None:
        self.temp_dir = self.create_temp_dir("api-integration")
        root = self.temp_dir
        knowledge_dir = root / "docs" / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        (knowledge_dir / "demo.md").write_text(
            "Keywords: login, selenium, explicit wait\n\n"
            "Use explicit waits before interacting with elements.",
            encoding="utf-8",
        )
        self.settings = Settings(
            DEEPSEEK_API_KEY=None,
            SQLITE_DB_PATH=str(root / "data" / "app.db"),
            VECTOR_STORE_DIR=str(root / "data" / "rag"),
            KNOWLEDGE_BASE_DIR=str(knowledge_dir),
            EXECUTIONS_DIR=str(root / "runs"),
        )
        initialize_database(self.settings)
        self.client = TestClient(create_app(self.settings))
        self.strategy = StrategyService()
        self.test_case_repo = TestCaseRepository(self.settings)
        self.execution_repo = ExecutionRepository(self.settings)

    def _create_test_case(self, prompt: str = "Open login page and verify dashboard") -> dict:
        """Helper: insert a test case directly via repository and return its dict."""
        ctx = self.strategy.analyze_generation(prompt)
        record = self.test_case_repo.create(
            title=prompt[:60],
            prompt=prompt,
            generated_code="print('Test Completed')",
            raw_output="print('Test Completed')",
            rag_context="Use explicit waits.",
            requested_strategy=ctx.requested_strategy,
            effective_strategy=ctx.effective_strategy,
        )
        return {"id": record.id, "prompt": prompt, "strategy": ctx}

    # ── GET /test-cases/{id} ──

    def test_get_test_case_returns_saved_record(self) -> None:
        case = self._create_test_case()
        resp = self.client.get(f"/api/v1/test-cases/{case['id']}")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["id"], case["id"])
        self.assertEqual(payload["prompt"], case["prompt"])

    def test_get_test_case_returns_404_for_unknown_id(self) -> None:
        resp = self.client.get("/api/v1/test-cases/nonexistent-id")
        self.assertEqual(resp.status_code, 404)

    # ── POST /executions ──

    def test_create_execution_starts_background_run(self) -> None:
        case = self._create_test_case()
        resp = self.client.post(
            "/api/v1/executions",
            json={"test_case_id": case["id"]},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["test_case_id"], case["id"])
        self.assertIn(payload["status"], ("queued", "running", "completed", "failed", "blocked"))

    def test_create_execution_rejects_missing_test_case(self) -> None:
        resp = self.client.post(
            "/api/v1/executions",
            json={"test_case_id": "nonexistent"},
        )
        self.assertEqual(resp.status_code, 404)

    # ── GET /executions/{id} ──

    def test_get_execution_returns_record(self) -> None:
        case = self._create_test_case()
        exec_record = self.execution_repo.create(
            test_case_id=case["id"],
            executed_code="print('Test Completed')",
            requested_strategy=case["strategy"].requested_strategy,
            effective_strategy=case["strategy"].effective_strategy,
            site_profile=None,
        )
        resp = self.client.get(f"/api/v1/executions/{exec_record.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], exec_record.id)

    def test_get_execution_returns_404_for_unknown_id(self) -> None:
        resp = self.client.get("/api/v1/executions/nonexistent")
        self.assertEqual(resp.status_code, 404)

    # ── GET /executions (list + pagination + filter) ──

    def test_list_executions_returns_paginated_results(self) -> None:
        case = self._create_test_case()
        for _ in range(3):
            rec = self.execution_repo.create(
                test_case_id=case["id"],
                executed_code="print('Test Completed')",
                requested_strategy=case["strategy"].requested_strategy,
                effective_strategy=case["strategy"].effective_strategy,
                site_profile=None,
            )
            self.execution_repo.mark_running(rec.id, run_directory="r", script_path="s")
            self.execution_repo.mark_finished(rec.id, status="completed")

        resp = self.client.get("/api/v1/executions", params={"limit": 2, "offset": 0})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["limit"], 2)

    def test_list_executions_filters_by_status(self) -> None:
        case = self._create_test_case()
        rec = self.execution_repo.create(
            test_case_id=case["id"],
            executed_code="print('Test Completed')",
            requested_strategy=case["strategy"].requested_strategy,
            effective_strategy=case["strategy"].effective_strategy,
            site_profile=None,
        )
        self.execution_repo.mark_running(rec.id, run_directory="r", script_path="s")
        self.execution_repo.mark_finished(rec.id, status="failed", error="boom")

        resp = self.client.get("/api/v1/executions", params={"status": "completed", "limit": 10, "offset": 0})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["status_filter"], "completed")
        self.assertEqual(payload["total"], 0)

    # ── GET /executions/stats ──

    def test_stats_returns_metrics_structure(self) -> None:
        resp = self.client.get("/api/v1/executions/stats")
        self.assertEqual(resp.status_code, 200)
        metrics = resp.json()["metrics"]
        self.assertIn("generated_count", metrics)
        self.assertIn("first_pass_success_rate", metrics)
        self.assertIn("final_success_rate", metrics)
        self.assertIn("trend", metrics)

    def test_stats_reflect_completed_execution(self) -> None:
        case = self._create_test_case()
        rec = self.execution_repo.create(
            test_case_id=case["id"],
            executed_code="print('Test Completed')",
            requested_strategy=case["strategy"].requested_strategy,
            effective_strategy=case["strategy"].effective_strategy,
            site_profile=None,
        )
        self.execution_repo.mark_running(rec.id, run_directory="r", script_path="s")
        self.execution_repo.mark_finished(rec.id, status="completed")

        resp = self.client.get("/api/v1/executions/stats")
        metrics = resp.json()["metrics"]
        self.assertGreaterEqual(metrics["execution_count"], 1)
        self.assertGreaterEqual(metrics["first_pass_success_count"], 1)

    # ── DELETE /executions/{id} (cancel) ──

    def test_cancel_queued_execution(self) -> None:
        # Trigger lazy container creation (which runs recover_interrupted)
        # before inserting the record we want to cancel.
        self.client.get("/api/v1/health")

        case = self._create_test_case()
        rec = self.execution_repo.create(
            test_case_id=case["id"],
            executed_code="print('Test Completed')",
            requested_strategy=case["strategy"].requested_strategy,
            effective_strategy=case["strategy"].effective_strategy,
            site_profile=None,
        )
        resp = self.client.delete(f"/api/v1/executions/{rec.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "cancelled")

    def test_cancel_already_finished_execution_returns_409(self) -> None:
        case = self._create_test_case()
        rec = self.execution_repo.create(
            test_case_id=case["id"],
            executed_code="print('Test Completed')",
            requested_strategy=case["strategy"].requested_strategy,
            effective_strategy=case["strategy"].effective_strategy,
            site_profile=None,
        )
        self.execution_repo.mark_running(rec.id, run_directory="r", script_path="s")
        self.execution_repo.mark_finished(rec.id, status="completed")

        resp = self.client.delete(f"/api/v1/executions/{rec.id}")
        self.assertEqual(resp.status_code, 409)

    # ── GET /health ──

    def test_health_endpoint_returns_component_statuses(self) -> None:
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        for key in ("backend", "model", "knowledge_base", "storage"):
            self.assertIn(key, payload)
            self.assertIn("status", payload[key])

    # ── POST /knowledge/rebuild ──

    def test_knowledge_rebuild_indexes_and_returns_count(self) -> None:
        resp = self.client.post("/api/v1/knowledge/rebuild")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["ready"])
        self.assertGreaterEqual(payload["document_count"], 1)

    # ── Full chain: test-case → execution → stats ──

    def test_full_chain_test_case_to_execution_to_stats(self) -> None:
        case = self._create_test_case("Open Baidu, search for DeepSeek, verify results")
        rec = self.execution_repo.create(
            test_case_id=case["id"],
            executed_code="print('Test Completed')",
            requested_strategy=case["strategy"].requested_strategy,
            effective_strategy=case["strategy"].effective_strategy,
            site_profile=case["strategy"].site_profile,
        )
        self.execution_repo.mark_running(rec.id, run_directory="r", script_path="s")
        self.execution_repo.mark_finished(rec.id, status="completed")

        case_resp = self.client.get(f"/api/v1/test-cases/{case['id']}")
        self.assertEqual(case_resp.status_code, 200)

        exec_resp = self.client.get(f"/api/v1/executions/{rec.id}")
        self.assertEqual(exec_resp.status_code, 200)
        self.assertEqual(exec_resp.json()["status"], "completed")

        list_resp = self.client.get("/api/v1/executions", params={"limit": 10, "offset": 0})
        self.assertEqual(list_resp.status_code, 200)
        self.assertGreaterEqual(list_resp.json()["total"], 1)

        stats_resp = self.client.get("/api/v1/executions/stats")
        self.assertEqual(stats_resp.status_code, 200)
        self.assertGreaterEqual(stats_resp.json()["metrics"]["final_success_count"], 1)


if __name__ == "__main__":
    unittest.main()
