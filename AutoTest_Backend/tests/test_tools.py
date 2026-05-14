"""Tests for agent-callable tool wrappers (generate, execute, knowledge, validate, diagnose, memory)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from . import _bootstrap  # noqa: F401

from app.schemas.generate import TestCaseRead
from app.schemas.execution import ExecutionRead
from app.services.rag_service import RAGSearchResult
from app.services.agent_memory_service import MemorySearchResult
from app.tools.base import ToolResult
from app.tools.generate_tool import GenerateScriptTool
from app.tools.execute_tool import ExecuteScriptTool, GetExecutionResultTool
from app.tools.knowledge_tool import SearchKnowledgeTool
from app.tools.validate_tool import ValidateCodeTool
from app.tools.diagnose_tool import DiagnoseFailureTool
from app.tools.memory_tool import SearchMemoryTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_test_case(**overrides) -> MagicMock:
    defaults = {
        "id": "tc-001",
        "title": "Test",
        "prompt": "test prompt",
        "generated_code": "print('hello')",
        "raw_output": "```python\nprint('hello')\n```",
        "rag_context": "[]",
        "status": "generated",
        "created_at": "2025-01-01T00:00:00",
        "requested_strategy": "interaction_first",
        "effective_strategy": "interaction_first",
    }
    defaults.update(overrides)
    return MagicMock(spec=TestCaseRead, **defaults)


def _mock_execution(**overrides) -> MagicMock:
    defaults = {
        "id": "exec-001",
        "test_case_id": "tc-001",
        "test_case_title": "Test",
        "executed_code": "print('hello')",
        "status": "completed",
        "run_directory": "/tmp",
        "script_path": "/tmp/script.py",
        "logs": "Test Completed",
        "error": None,
        "validation_errors": [],
        "created_at": "2025-01-01T00:00:00",
        "started_at": "2025-01-01T00:00:01",
        "finished_at": "2025-01-01T00:00:05",
        "requested_strategy": "interaction_first",
        "effective_strategy": "interaction_first",
        "self_heal_triggered": False,
        "self_heal_count": 0,
        "healed": False,
    }
    defaults.update(overrides)
    return MagicMock(spec=ExecutionRead, **defaults)


# ---------------------------------------------------------------------------
# GenerateScriptTool
# ---------------------------------------------------------------------------


class GenerateScriptToolTests(unittest.TestCase):
    def setUp(self):
        self.gen_service = MagicMock()
        self.tool = GenerateScriptTool(self.gen_service)

    def test_name_and_description(self):
        self.assertEqual(self.tool.name, "generate_selenium_script")
        self.assertIn("Selenium", self.tool.description)

    def test_parameters_schema_requires_prompt(self):
        self.assertEqual(self.tool.parameters_schema["type"], "object")
        self.assertIn("prompt", self.tool.parameters_schema["required"])

    def test_execute_success(self):
        record = _mock_test_case(generated_code="print('repaired')")
        rag_result = RAGSearchResult(
            context="knowledge context",
            sources=["doc1.md"],
            result_count=1,
            retrieval_mode="hybrid_rerank",
        )
        self.gen_service.generate.return_value = (record, rag_result)

        result = self.tool.execute(prompt="打开百度搜索 Selenium")

        self.assertTrue(result.success)
        self.assertEqual(result.data["test_case_id"], "tc-001")
        self.assertEqual(result.data["generated_code"], "print('repaired')")
        self.assertEqual(result.data["retrieval_mode"], "hybrid_rerank")

    def test_execute_with_retrieval_mode(self):
        record = _mock_test_case()
        rag_result = RAGSearchResult(context="", sources=[], result_count=0, retrieval_mode="vector")
        self.gen_service.generate.return_value = (record, rag_result)

        result = self.tool.execute(prompt="test", retrieval_mode="vector")
        self.gen_service.generate.assert_called_once_with("test", retrieval_mode="vector")

    def test_execute_failure(self):
        self.gen_service.generate.side_effect = RuntimeError("LLM down")

        result = self.tool.execute(prompt="test prompt here")
        self.assertFalse(result.success)
        self.assertIn("LLM down", result.error)


# ---------------------------------------------------------------------------
# ExecuteScriptTool
# ---------------------------------------------------------------------------


class ExecuteScriptToolTests(unittest.TestCase):
    def setUp(self):
        self.exec_service = MagicMock()
        self.tool = ExecuteScriptTool(self.exec_service)

    def test_name(self):
        self.assertEqual(self.tool.name, "execute_script")

    def test_parameters_requires_test_case_id(self):
        self.assertIn("test_case_id", self.tool.parameters_schema["required"])

    def test_execute_success(self):
        self.exec_service.create_execution.return_value = _mock_execution()

        result = self.tool.execute(test_case_id="tc-001")

        self.assertTrue(result.success)
        self.assertEqual(result.data["execution_id"], "exec-001")
        self.assertEqual(result.data["status"], "completed")

    def test_execute_with_code_override(self):
        self.exec_service.create_execution.return_value = _mock_execution()

        result = self.tool.execute(test_case_id="tc-001", code_override="print('fixed')")

        self.exec_service.create_execution.assert_called_once_with(
            test_case_id="tc-001", code_override="print('fixed')"
        )

    def test_execute_failure(self):
        self.exec_service.create_execution.side_effect = ValueError("Invalid ID")

        result = self.tool.execute(test_case_id="bad-id")
        self.assertFalse(result.success)
        self.assertIn("Invalid ID", result.error)


# ---------------------------------------------------------------------------
# GetExecutionResultTool
# ---------------------------------------------------------------------------


class GetExecutionResultToolTests(unittest.TestCase):
    def setUp(self):
        self.exec_service = MagicMock()
        self.tool = GetExecutionResultTool(self.exec_service)

    def test_name(self):
        self.assertEqual(self.tool.name, "get_execution_result")

    def test_completed_status(self):
        self.exec_service.get_execution.return_value = _mock_execution(status="completed")

        result = self.tool.execute(execution_id="exec-001")
        self.assertTrue(result.success)
        self.assertIn("succeeded", result.summary)

    def test_failed_status(self):
        self.exec_service.get_execution.return_value = _mock_execution(
            status="failed", error="NoSuchElementException"
        )

        result = self.tool.execute(execution_id="exec-001")
        self.assertTrue(result.success)
        self.assertIn("failed", result.summary)
        self.assertIn("NoSuchElementException", result.summary)

    def test_running_status(self):
        self.exec_service.get_execution.return_value = _mock_execution(status="running")

        result = self.tool.execute(execution_id="exec-001")
        self.assertTrue(result.success)
        self.assertIn("still running", result.summary)

    def test_healed_completed(self):
        self.exec_service.get_execution.return_value = _mock_execution(
            status="healed_completed", healed=True, self_heal_count=1
        )

        result = self.tool.execute(execution_id="exec-001")
        self.assertTrue(result.success)
        self.assertEqual(result.data["healed"], True)
        self.assertEqual(result.data["self_heal_count"], 1)


# ---------------------------------------------------------------------------
# SearchKnowledgeTool
# ---------------------------------------------------------------------------


class SearchKnowledgeToolTests(unittest.TestCase):
    def setUp(self):
        self.rag_service = MagicMock()
        self.tool = SearchKnowledgeTool(self.rag_service)

    def test_name(self):
        self.assertEqual(self.tool.name, "search_knowledge")

    def test_parameters_requires_query(self):
        self.assertIn("query", self.tool.parameters_schema["required"])

    def test_execute_success(self):
        self.rag_service.search.return_value = RAGSearchResult(
            context="# Login Flow\ndocument content",
            sources=["login_flows.md"],
            result_count=3,
            retrieval_mode="hybrid",
        )

        result = self.tool.execute(query="vue admin login")

        self.assertTrue(result.success)
        self.assertEqual(result.data["result_count"], 3)
        self.assertEqual(result.data["retrieval_mode"], "hybrid")
        self.assertIn("Login Flow", result.data["context"])

    def test_execute_with_retrieval_mode(self):
        self.rag_service.search.return_value = RAGSearchResult(
            context="", sources=[], result_count=0, retrieval_mode="vector"
        )

        self.tool.execute(query="test", retrieval_mode="vector")
        self.rag_service.search.assert_called_once_with("test", retrieval_mode="vector")

    def test_execute_failure(self):
        self.rag_service.search.side_effect = RuntimeError("ChromaDB unavailable")

        result = self.tool.execute(query="test query")
        self.assertFalse(result.success)
        self.assertIn("ChromaDB", result.error)


# ---------------------------------------------------------------------------
# ValidateCodeTool
# ---------------------------------------------------------------------------


class ValidateCodeToolTests(unittest.TestCase):
    def setUp(self):
        self.tool = ValidateCodeTool()

    def test_name(self):
        self.assertEqual(self.tool.name, "validate_code")

    def test_safe_code_passes(self):
        result = self.tool.execute(code="print('hello world')")
        self.assertTrue(result.success)
        self.assertTrue(result.data["safe"])
        self.assertEqual(result.data["validation_errors"], [])

    def test_unsafe_code_returns_errors(self):
        result = self.tool.execute(code="import os\nos.system('rm -rf /')")
        self.assertTrue(result.success)
        self.assertFalse(result.data["safe"])
        self.assertGreater(len(result.data["validation_errors"]), 0)


# ---------------------------------------------------------------------------
# DiagnoseFailureTool
# ---------------------------------------------------------------------------


class DiagnoseFailureToolTests(unittest.TestCase):
    def setUp(self):
        self.tool = DiagnoseFailureTool(llm_service=None)

    def test_name(self):
        self.assertEqual(self.tool.name, "diagnose_failure")

    def test_execute_with_error(self):
        result = self.tool.execute(
            error="NoSuchElementException: unable to locate element #kw",
            logs="navigated to page",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["failure_type"], "selector_not_found")
        self.assertIn("source", result.data)

    def test_execute_with_validation_errors(self):
        result = self.tool.execute(
            validation_errors=["import os is not allowed"],
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["failure_type"], "safety_blocked")

    def test_execute_empty_inputs(self):
        result = self.tool.execute()
        self.assertTrue(result.success)
        self.assertEqual(result.data["failure_type"], "unknown_failure")

    def test_execute_with_llm(self):
        llm = MagicMock()
        import json
        llm.agent_chat.return_value = json.dumps({
            "failure_type": "wait_timeout",
            "failure_signal": "timed out",
            "root_cause_analysis": "Page load too slow",
            "repair_strategy": "Add explicit wait",
            "confidence": 0.9,
            "suggested_selectors": [],
        })
        tool = DiagnoseFailureTool(llm_service=llm)
        result = tool.execute(error="TimeoutException: timed out after 10s")
        self.assertTrue(result.success)

    def test_execute_failure(self):
        tool = DiagnoseFailureTool(diagnostic_service=None, llm_service=None)
        result = tool.execute(error="something")
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# SearchMemoryTool
# ---------------------------------------------------------------------------


class SearchMemoryToolTests(unittest.TestCase):
    def setUp(self):
        self.memory_service = MagicMock()
        self.tool = SearchMemoryTool(self.memory_service)

    def test_name(self):
        self.assertEqual(self.tool.name, "search_memory")

    def test_empty_query_rejected(self):
        result = self.tool.execute(query="   ")
        self.assertFalse(result.success)
        self.assertIn("empty", result.error)

    def test_execute_with_results(self):
        self.memory_service.search_similar.return_value = MemorySearchResult(
            cards=[
                {"source": "heal_001.md", "card_type": "heal", "distance": 0.2, "content": "Use #kw"},
                {"source": "trap_001.md", "card_type": "trap", "distance": 0.4, "content": "Avoid button[type=submit]"},
            ],
            context="# Heal: Use #kw\n\n# Trap: Avoid button[type=submit]",
            result_count=2,
        )

        result = self.tool.execute(query="NoSuchElementException on Baidu")

        self.assertTrue(result.success)
        self.assertEqual(result.data["result_count"], 2)
        self.assertEqual(len(result.data["cards"]), 2)
        self.assertEqual(result.data["cards"][0]["card_type"], "heal")

    def test_execute_no_results(self):
        self.memory_service.search_similar.return_value = MemorySearchResult(
            cards=[], context="", result_count=0
        )

        result = self.tool.execute(query="something new")
        self.assertTrue(result.success)
        self.assertEqual(result.data["result_count"], 0)
        self.assertIn("No similar", result.summary)

    def test_execute_with_card_type_filter(self):
        self.memory_service.search_similar.return_value = MemorySearchResult(
            cards=[], context="", result_count=0
        )

        self.tool.execute(query="test", n_results=5, card_type="heal")
        self.memory_service.search_similar.assert_called_once_with(
            query="test", n_results=5, card_type="heal"
        )

    def test_execute_failure(self):
        self.memory_service.search_similar.side_effect = RuntimeError("ChromaDB down")

        result = self.tool.execute(query="test query here")
        self.assertFalse(result.success)
        self.assertIn("ChromaDB", result.error)


if __name__ == "__main__":
    unittest.main()
