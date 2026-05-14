"""Tests for TaskAnalyzer: LLM-driven task analysis with fallback."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

from . import _bootstrap  # noqa: F401 — path bootstrap

from app.services.task_analyzer import TaskAnalyzer, TaskAnalysis, TargetSite, _str_list


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_llm(response_dict: dict) -> MagicMock:
    """Return a mock LLMService whose agent_chat returns the given dict as JSON."""
    llm = MagicMock()
    llm.agent_chat = MagicMock(return_value=json.dumps(response_dict, ensure_ascii=False))
    return llm


def _mock_llm_raw(raw_str: str) -> MagicMock:
    llm = MagicMock()
    llm.agent_chat = MagicMock(return_value=raw_str)
    return llm


# ---------------------------------------------------------------------------
# TaskAnalysis data-class tests
# ---------------------------------------------------------------------------


class TaskAnalysisTests(unittest.TestCase):
    def test_to_dict(self):
        ta = TaskAnalysis(
            intent="search",
            target_site=TargetSite(url="https://www.baidu.com", name="Baidu"),
            steps=["Open Baidu", "Type keyword", "Click search"],
            preconditions=["Browser available"],
            success_criteria=["Results page shows keyword"],
            complexity="multi_step",
        )
        d = ta.to_dict()
        self.assertEqual(d["intent"], "search")
        self.assertEqual(d["complexity"], "multi_step")
        self.assertEqual(len(d["steps"]), 3)
        self.assertEqual(d["target_site"]["url"], "https://www.baidu.com")

    def test_to_prompt_block_contains_key_fields(self):
        ta = TaskAnalysis(
            intent="login",
            target_site=TargetSite(url="http://localhost:9528", name="vue-admin"),
            steps=["Open login page", "Enter credentials", "Submit"],
            success_criteria=["Dashboard visible"],
            complexity="multi_step",
        )
        block = ta.to_prompt_block()
        self.assertIn("Intent: login", block)
        self.assertIn("Complexity: multi_step", block)
        self.assertIn("http://localhost:9528", block)
        self.assertIn("1. Open login page", block)
        self.assertIn("Dashboard visible", block)

    def test_to_dict_defaults(self):
        ta = TaskAnalysis(intent="other")
        d = ta.to_dict()
        self.assertEqual(d["intent"], "other")
        self.assertEqual(d["steps"], [])
        self.assertEqual(d["complexity"], "simple")


# ---------------------------------------------------------------------------
# TaskAnalyzer — happy path (mocked LLM)
# ---------------------------------------------------------------------------


class TaskAnalyzerLLMTests(unittest.TestCase):
    def test_analyze_search_prompt(self):
        response = {
            "intent": "search",
            "target_site": {"url": "https://www.baidu.com", "name": "Baidu"},
            "steps": ["Open Baidu homepage", "Type 'Selenium' in search box", "Click search button"],
            "preconditions": [],
            "success_criteria": ["Search results page contains 'Selenium'"],
            "complexity": "multi_step",
        }
        analyzer = TaskAnalyzer(_mock_llm(response))
        result = analyzer.analyze("打开百度搜索 Selenium")

        self.assertEqual(result.intent, "search")
        self.assertEqual(result.complexity, "multi_step")
        self.assertEqual(len(result.steps), 3)
        self.assertEqual(result.target_site.url, "https://www.baidu.com")
        self.assertEqual(result.target_site.name, "Baidu")

    def test_analyze_login_prompt(self):
        response = {
            "intent": "login",
            "target_site": {"url": "http://localhost:9528", "name": "vue-admin-template"},
            "steps": ["Open login page", "Enter admin/111111", "Click login"],
            "preconditions": ["vue-admin-template running on localhost:9528"],
            "success_criteria": ["Dashboard page displayed"],
            "complexity": "multi_step",
        }
        analyzer = TaskAnalyzer(_mock_llm(response))
        result = analyzer.analyze("用 admin/111111 登录 vue-admin-template")

        self.assertEqual(result.intent, "login")
        self.assertIn("admin", result.steps[1].lower())

    def test_analyze_simple_navigate(self):
        response = {
            "intent": "navigate",
            "steps": ["Open example.com"],
            "success_criteria": ["Page loads successfully"],
            "complexity": "simple",
        }
        analyzer = TaskAnalyzer(_mock_llm(response))
        result = analyzer.analyze("Open example.com")
        self.assertEqual(result.intent, "navigate")
        self.assertEqual(result.complexity, "simple")

    def test_analyze_complex_flow(self):
        response = {
            "intent": "multi_step",
            "target_site": {"url": "http://localhost:9528"},
            "steps": [
                "Open login page",
                "Login with admin/111111",
                "Wait for dashboard",
                "Navigate to user management",
                "Search user test",
                "Verify search results",
            ],
            "preconditions": ["App running"],
            "success_criteria": ["User 'test' visible in results"],
            "complexity": "complex_flow",
        }
        analyzer = TaskAnalyzer(_mock_llm(response))
        result = analyzer.analyze(
            "打开 vue-admin-template，用 admin/111111 登录，进入用户管理页面，搜索用户 test"
        )
        self.assertEqual(result.complexity, "complex_flow")
        self.assertEqual(len(result.steps), 6)


# ---------------------------------------------------------------------------
# Parsing edge cases
# ---------------------------------------------------------------------------


class TaskAnalyzerParsingTests(unittest.TestCase):
    def test_handles_markdown_fenced_json(self):
        fenced = '```json\n{"intent":"search","steps":["step1"],"success_criteria":["ok"],"complexity":"simple"}\n```'
        analyzer = TaskAnalyzer(_mock_llm_raw(fenced))
        result = analyzer.analyze("test")
        self.assertEqual(result.intent, "search")

    def test_handles_json_embedded_in_text(self):
        mixed = 'Here is the analysis:\n{"intent":"login","steps":["open"],"success_criteria":["done"],"complexity":"simple"}\nEnd.'
        analyzer = TaskAnalyzer(_mock_llm_raw(mixed))
        result = analyzer.analyze("test")
        self.assertEqual(result.intent, "login")

    def test_invalid_complexity_normalized(self):
        response = {
            "intent": "search",
            "steps": ["s1"],
            "success_criteria": ["c1"],
            "complexity": "INVALID",
        }
        analyzer = TaskAnalyzer(_mock_llm(response))
        result = analyzer.analyze("test")
        self.assertEqual(result.complexity, "simple")

    def test_missing_target_site_defaults_to_empty(self):
        response = {
            "intent": "verify",
            "steps": ["check something"],
            "success_criteria": ["pass"],
            "complexity": "simple",
        }
        analyzer = TaskAnalyzer(_mock_llm(response))
        result = analyzer.analyze("verify the page")
        self.assertEqual(result.target_site.url, "")
        self.assertEqual(result.target_site.name, "")


# ---------------------------------------------------------------------------
# Fallback (LLM fails)
# ---------------------------------------------------------------------------


class TaskAnalyzerFallbackTests(unittest.TestCase):
    def test_fallback_on_llm_exception(self):
        llm = MagicMock()
        llm.agent_chat = MagicMock(side_effect=RuntimeError("LLM unavailable"))
        analyzer = TaskAnalyzer(llm)
        result = analyzer.analyze("打开百度搜索 Selenium")
        self.assertEqual(result.intent, "search")
        self.assertEqual(result.complexity, "simple")
        self.assertGreater(len(result.steps), 0)

    def test_fallback_on_garbage_response(self):
        analyzer = TaskAnalyzer(_mock_llm_raw("NOT JSON AT ALL!!!"))
        result = analyzer.analyze("Login to the system")
        self.assertEqual(result.intent, "login")

    def test_fallback_login_intent(self):
        llm = MagicMock()
        llm.agent_chat = MagicMock(side_effect=Exception("fail"))
        analyzer = TaskAnalyzer(llm)
        result = analyzer.analyze("登录系统")
        self.assertEqual(result.intent, "login")

    def test_fallback_navigate_intent(self):
        llm = MagicMock()
        llm.agent_chat = MagicMock(side_effect=Exception("fail"))
        analyzer = TaskAnalyzer(llm)
        result = analyzer.analyze("打开 example.com")
        self.assertEqual(result.intent, "navigate")

    def test_fallback_other_intent(self):
        llm = MagicMock()
        llm.agent_chat = MagicMock(side_effect=Exception("fail"))
        analyzer = TaskAnalyzer(llm)
        result = analyzer.analyze("do something random")
        self.assertEqual(result.intent, "other")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


class StrListTests(unittest.TestCase):
    def test_normal_list(self):
        self.assertEqual(_str_list(["a", "b"]), ["a", "b"])

    def test_filters_falsy(self):
        self.assertEqual(_str_list(["a", "", None, "b"]), ["a", "b"])

    def test_non_list_returns_empty(self):
        self.assertEqual(_str_list("not a list"), [])
        self.assertEqual(_str_list(None), [])

    def test_coerces_ints(self):
        self.assertEqual(_str_list([1, 2]), ["1", "2"])


if __name__ == "__main__":
    unittest.main()
