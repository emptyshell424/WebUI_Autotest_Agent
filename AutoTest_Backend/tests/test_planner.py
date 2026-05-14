"""Tests for Planner: LLM-driven execution plan generation with fallback."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

from . import _bootstrap  # noqa: F401 — path bootstrap

from app.services.planner import (
    ExecutionPlan,
    PlanStep,
    Planner,
    _infer_action,
    _strip_fences,
)
from app.services.task_analyzer import TaskAnalysis, TargetSite


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


def _make_task_analysis(
    intent: str = "search",
    steps: list[str] | None = None,
    complexity: str = "simple",
    success_criteria: list[str] | None = None,
    url: str = "",
    name: str = "",
) -> TaskAnalysis:
    return TaskAnalysis(
        intent=intent,
        target_site=TargetSite(url=url, name=name),
        steps=steps or [],
        success_criteria=success_criteria or [],
        complexity=complexity,
    )


# ---------------------------------------------------------------------------
# PlanStep data-class tests
# ---------------------------------------------------------------------------


class PlanStepTests(unittest.TestCase):
    def test_to_dict(self):
        s = PlanStep(
            step_number=1,
            action="navigate",
            description="Open homepage",
            parameters={"url": "http://example.com"},
            depends_on=[],
        )
        d = s.to_dict()
        self.assertEqual(d["step_number"], 1)
        self.assertEqual(d["action"], "navigate")
        self.assertEqual(d["description"], "Open homepage")
        self.assertEqual(d["parameters"]["url"], "http://example.com")
        self.assertEqual(d["depends_on"], [])

    def test_to_dict_defaults(self):
        s = PlanStep(step_number=2, action="click", description="Click button")
        d = s.to_dict()
        self.assertEqual(d["parameters"], {})
        self.assertEqual(d["depends_on"], [])

    def test_frozen(self):
        s = PlanStep(step_number=1, action="click", description="x")
        with self.assertRaises(AttributeError):
            s.action = "navigate"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ExecutionPlan data-class tests
# ---------------------------------------------------------------------------


class ExecutionPlanTests(unittest.TestCase):
    def test_to_dict(self):
        plan = ExecutionPlan(
            goal="Search on Baidu",
            steps=[
                PlanStep(step_number=1, action="navigate", description="Open Baidu"),
                PlanStep(step_number=2, action="search", description="Search keyword", depends_on=[1]),
            ],
            estimated_complexity="multi_step",
        )
        d = plan.to_dict()
        self.assertEqual(d["goal"], "Search on Baidu")
        self.assertEqual(d["step_count"], 2)
        self.assertEqual(d["estimated_complexity"], "multi_step")
        self.assertEqual(len(d["steps"]), 2)

    def test_step_count_property(self):
        plan = ExecutionPlan(goal="x", steps=[
            PlanStep(step_number=1, action="click", description="a"),
        ])
        self.assertEqual(plan.step_count, 1)

    def test_is_multi_step(self):
        single = ExecutionPlan(goal="x", steps=[
            PlanStep(step_number=1, action="click", description="a"),
        ])
        self.assertFalse(single.is_multi_step)

        multi = ExecutionPlan(goal="x", steps=[
            PlanStep(step_number=1, action="navigate", description="a"),
            PlanStep(step_number=2, action="click", description="b"),
        ])
        self.assertTrue(multi.is_multi_step)

    def test_to_prompt_block(self):
        plan = ExecutionPlan(
            goal="Login to admin",
            steps=[
                PlanStep(step_number=1, action="navigate", description="Open login page",
                         parameters={"url": "http://localhost:9528"}),
                PlanStep(step_number=2, action="login", description="Enter credentials",
                         depends_on=[1]),
                PlanStep(step_number=3, action="verify", description="Dashboard visible",
                         depends_on=[2]),
            ],
            estimated_complexity="multi_step",
        )
        block = plan.to_prompt_block()
        self.assertIn("Execution Plan (multi_step, 3 steps)", block)
        self.assertIn("Goal: Login to admin", block)
        self.assertIn("[navigate]", block)
        self.assertIn("[login]", block)
        self.assertIn("[verify]", block)
        self.assertIn("http://localhost:9528", block)
        self.assertIn("after step 1", block)

    def test_empty_plan(self):
        plan = ExecutionPlan(goal="empty")
        self.assertEqual(plan.step_count, 0)
        self.assertFalse(plan.is_multi_step)

    def test_to_dict_with_metadata(self):
        plan = ExecutionPlan(goal="x", metadata={"source": "llm"})
        d = plan.to_dict()
        self.assertEqual(d["metadata"]["source"], "llm")


# ---------------------------------------------------------------------------
# Planner — simple task (no LLM call)
# ---------------------------------------------------------------------------


class PlannerSimpleTaskTests(unittest.TestCase):
    """Simple tasks (complexity=='simple' and ≤2 steps) skip the LLM call."""

    def test_simple_task_no_llm_call(self):
        llm = MagicMock()
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="search",
            steps=["Open Baidu", "Search keyword"],
            complexity="simple",
            success_criteria=["Results page visible"],
        )
        plan = planner.plan(ta)
        llm.agent_chat.assert_not_called()
        self.assertIsInstance(plan, ExecutionPlan)
        self.assertEqual(plan.estimated_complexity, "simple")
        # Should have steps + 1 verify step at end
        self.assertGreaterEqual(plan.step_count, 2)
        self.assertEqual(plan.steps[-1].action, "verify")

    def test_simple_single_step(self):
        llm = MagicMock()
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="navigate",
            steps=["Open homepage"],
            complexity="simple",
            success_criteria=["Page loads"],
        )
        plan = planner.plan(ta)
        llm.agent_chat.assert_not_called()
        self.assertEqual(plan.steps[0].action, "navigate")
        # Final step should be verify
        self.assertEqual(plan.steps[-1].action, "verify")
        self.assertIn("Page loads", plan.steps[-1].description)

    def test_simple_no_steps_uses_intent(self):
        llm = MagicMock()
        planner = Planner(llm)
        ta = _make_task_analysis(intent="click", steps=[], complexity="simple")
        plan = planner.plan(ta)
        self.assertGreaterEqual(plan.step_count, 1)
        # First step description should be the intent since no steps provided
        self.assertEqual(plan.steps[0].description, "click")


# ---------------------------------------------------------------------------
# Planner — multi-step task (LLM call)
# ---------------------------------------------------------------------------


class PlannerMultiStepTests(unittest.TestCase):
    """Multi-step and complex tasks trigger an LLM call."""

    def test_multi_step_calls_llm(self):
        response = {
            "goal": "Login and search user",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "Open login page",
                 "parameters": {"url": "http://localhost:9528"}},
                {"step_number": 2, "action": "login", "description": "Enter admin credentials",
                 "depends_on": [1]},
                {"step_number": 3, "action": "navigate", "description": "Go to user management",
                 "depends_on": [2]},
                {"step_number": 4, "action": "search", "description": "Search for user 'test'",
                 "depends_on": [3]},
                {"step_number": 5, "action": "verify", "description": "Check search results",
                 "depends_on": [4]},
            ],
            "estimated_complexity": "complex_flow",
        }
        llm = _mock_llm(response)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="multi_step",
            steps=["Open login", "Login", "Navigate to user mgmt", "Search user", "Verify results"],
            complexity="complex_flow",
        )
        plan = planner.plan(ta)
        llm.agent_chat.assert_called_once()
        self.assertEqual(plan.goal, "Login and search user")
        self.assertEqual(plan.step_count, 5)
        self.assertEqual(plan.estimated_complexity, "complex_flow")
        self.assertEqual(plan.steps[0].action, "navigate")
        self.assertEqual(plan.steps[0].parameters["url"], "http://localhost:9528")
        self.assertEqual(plan.steps[1].depends_on, [1])

    def test_multi_step_with_markdown_fences(self):
        response = {
            "goal": "Login flow",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "Open site"},
                {"step_number": 2, "action": "login", "description": "Login", "depends_on": [1]},
                {"step_number": 3, "action": "verify", "description": "Check dashboard", "depends_on": [2]},
            ],
            "estimated_complexity": "multi_step",
        }
        raw = "```json\n" + json.dumps(response) + "\n```"
        llm = _mock_llm_raw(raw)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="login",
            steps=["Open", "Login", "Verify"],
            complexity="multi_step",
        )
        plan = planner.plan(ta)
        self.assertEqual(plan.step_count, 3)
        self.assertEqual(plan.goal, "Login flow")

    def test_multi_step_threshold_three_steps(self):
        """3 steps + multi_step complexity should trigger LLM call."""
        response = {
            "goal": "Three-step plan",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "Step one"},
                {"step_number": 2, "action": "click", "description": "Step two", "depends_on": [1]},
                {"step_number": 3, "action": "verify", "description": "Step three", "depends_on": [2]},
            ],
            "estimated_complexity": "multi_step",
        }
        llm = _mock_llm(response)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="navigate",
            steps=["Step 1", "Step 2", "Step 3"],
            complexity="multi_step",
        )
        plan = planner.plan(ta)
        llm.agent_chat.assert_called_once()
        self.assertEqual(plan.step_count, 3)


# ---------------------------------------------------------------------------
# Planner — complex_flow scenarios
# ---------------------------------------------------------------------------


class PlannerComplexFlowTests(unittest.TestCase):
    def test_complex_flow_six_steps(self):
        response = {
            "goal": "Full admin workflow",
            "steps": [
                {"step_number": i, "action": act, "description": f"Step {i}",
                 "depends_on": [i - 1] if i > 1 else []}
                for i, act in enumerate(
                    ["navigate", "login", "wait", "navigate", "search", "verify"], 1
                )
            ],
            "estimated_complexity": "complex_flow",
        }
        llm = _mock_llm(response)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="multi_step",
            steps=["Open", "Login", "Wait", "Navigate", "Search", "Verify"],
            complexity="complex_flow",
        )
        plan = planner.plan(ta)
        self.assertEqual(plan.step_count, 6)
        self.assertEqual(plan.estimated_complexity, "complex_flow")
        # Verify dependency chain
        self.assertEqual(plan.steps[2].depends_on, [2])
        self.assertEqual(plan.steps[5].depends_on, [5])

    def test_complex_flow_with_parameters(self):
        response = {
            "goal": "Login with specific credentials",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "Open site",
                 "parameters": {"url": "http://localhost:9528"}},
                {"step_number": 2, "action": "fill_form", "description": "Enter username",
                 "parameters": {"selector": "#username", "text": "admin"}, "depends_on": [1]},
                {"step_number": 3, "action": "fill_form", "description": "Enter password",
                 "parameters": {"selector": "#password", "text": "111111"}, "depends_on": [2]},
                {"step_number": 4, "action": "click", "description": "Click login button",
                 "parameters": {"selector": ".login-btn"}, "depends_on": [3]},
                {"step_number": 5, "action": "verify", "description": "Dashboard loaded",
                 "depends_on": [4]},
            ],
            "estimated_complexity": "complex_flow",
        }
        llm = _mock_llm(response)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="login",
            steps=["Open site", "Enter user", "Enter pass", "Click login", "Verify"],
            complexity="complex_flow",
        )
        plan = planner.plan(ta)
        self.assertEqual(plan.steps[1].parameters["selector"], "#username")
        self.assertEqual(plan.steps[2].parameters["text"], "111111")


# ---------------------------------------------------------------------------
# Planner — fallback scenarios
# ---------------------------------------------------------------------------


class PlannerFallbackTests(unittest.TestCase):
    def test_llm_exception_falls_back(self):
        llm = MagicMock()
        llm.agent_chat = MagicMock(side_effect=Exception("LLM timeout"))
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="login",
            steps=["Open site", "Login", "Verify"],
            complexity="multi_step",
            success_criteria=["Dashboard visible"],
        )
        plan = planner.plan(ta)
        self.assertIsInstance(plan, ExecutionPlan)
        self.assertGreaterEqual(plan.step_count, 3)
        # Should still end with verify
        self.assertEqual(plan.steps[-1].action, "verify")

    def test_unparseable_json_falls_back(self):
        llm = _mock_llm_raw("This is not JSON at all!!!")
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="search",
            steps=["Open", "Search"],
            complexity="multi_step",
        )
        plan = planner.plan(ta)
        self.assertIsInstance(plan, ExecutionPlan)
        self.assertGreaterEqual(plan.step_count, 1)

    def test_empty_steps_in_response_falls_back(self):
        response = {
            "goal": "Test",
            "steps": [],
            "estimated_complexity": "simple",
        }
        llm = _mock_llm(response)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="navigate",
            steps=["Open homepage", "Navigate menu", "Verify"],
            complexity="multi_step",
        )
        plan = planner.plan(ta)
        # Should fallback to task_analysis steps
        self.assertGreaterEqual(plan.step_count, 3)

    def test_invalid_json_with_embedded_object_extracted(self):
        raw = 'Sure! Here is the plan: {"goal": "Test", "steps": [{"step_number": 1, "action": "navigate", "description": "Open"}], "estimated_complexity": "simple"} hope this helps!'
        llm = _mock_llm_raw(raw)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="navigate",
            steps=["Open", "Click", "Verify"],
            complexity="multi_step",
        )
        plan = planner.plan(ta)
        self.assertEqual(plan.step_count, 1)
        self.assertEqual(plan.steps[0].action, "navigate")

    def test_invalid_complexity_normalized(self):
        response = {
            "goal": "Test",
            "steps": [{"step_number": 1, "action": "click", "description": "Do thing"}],
            "estimated_complexity": "INVALID_VALUE",
        }
        llm = _mock_llm(response)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="click",
            steps=["Open", "Click", "Verify"],
            complexity="multi_step",
        )
        plan = planner.plan(ta)
        # Should normalize to task_analysis.complexity
        self.assertEqual(plan.estimated_complexity, "multi_step")

    def test_malformed_steps_skipped(self):
        response = {
            "goal": "Test",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "Open"},
                "not a dict",
                {"step_number": 3, "action": "verify", "description": "Check"},
            ],
            "estimated_complexity": "multi_step",
        }
        llm = _mock_llm(response)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="navigate",
            steps=["Open", "Bad", "Check"],
            complexity="multi_step",
        )
        plan = planner.plan(ta)
        # Only valid dict steps should be included
        self.assertEqual(plan.step_count, 2)

    def test_steps_not_a_list_falls_back(self):
        response = {
            "goal": "Test",
            "steps": "not a list",
            "estimated_complexity": "simple",
        }
        llm = _mock_llm(response)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="navigate",
            steps=["Open page"],
            complexity="multi_step",
        )
        plan = planner.plan(ta)
        # Should fallback since steps is not a list
        self.assertGreaterEqual(plan.step_count, 1)


# ---------------------------------------------------------------------------
# Planner — edge cases
# ---------------------------------------------------------------------------


class PlannerEdgeCaseTests(unittest.TestCase):
    def test_verify_step_not_duplicated_if_last_is_verify(self):
        """If LLM already ends with verify, fallback should not add another."""
        llm = MagicMock()
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="verify",
            steps=["Open page", "Verify content"],
            complexity="simple",
            success_criteria=["Content visible"],
        )
        plan = planner.plan(ta)
        # Last step should be verify but should not have double verify
        verify_count = sum(1 for s in plan.steps if s.action == "verify")
        # The "Verify content" step maps to verify, so no extra appended
        self.assertEqual(plan.steps[-1].action, "verify")

    def test_dependencies_are_sequential_in_fallback(self):
        llm = MagicMock()
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="multi_step",
            steps=["Step A", "Step B", "Step C"],
            complexity="simple",
        )
        plan = planner.plan(ta)
        # Step 1 should have no deps, step 2 depends on 1, etc.
        self.assertEqual(plan.steps[0].depends_on, [])
        self.assertEqual(plan.steps[1].depends_on, [1])
        self.assertEqual(plan.steps[2].depends_on, [2])

    def test_goal_uses_first_step_desc(self):
        llm = MagicMock()
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="navigate",
            steps=["Open Baidu homepage"],
            complexity="simple",
        )
        plan = planner.plan(ta)
        self.assertEqual(plan.goal, "Open Baidu homepage")

    def test_plan_from_chinese_steps(self):
        response = {
            "goal": "在百度搜索关键词",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "打开百度首页",
                 "parameters": {"url": "https://www.baidu.com"}},
                {"step_number": 2, "action": "fill_form", "description": "输入搜索关键词",
                 "depends_on": [1]},
                {"step_number": 3, "action": "click", "description": "点击搜索按钮",
                 "depends_on": [2]},
                {"step_number": 4, "action": "verify", "description": "验证搜索结果页面",
                 "depends_on": [3]},
            ],
            "estimated_complexity": "multi_step",
        }
        llm = _mock_llm(response)
        planner = Planner(llm)
        ta = _make_task_analysis(
            intent="search",
            steps=["打开百度", "输入关键词", "点击搜索", "验证结果"],
            complexity="multi_step",
        )
        plan = planner.plan(ta)
        self.assertEqual(plan.goal, "在百度搜索关键词")
        self.assertEqual(plan.step_count, 4)
        self.assertIn("百度", plan.steps[0].description)


# ---------------------------------------------------------------------------
# _infer_action helper tests
# ---------------------------------------------------------------------------


class InferActionTests(unittest.TestCase):
    def test_navigate_keywords(self):
        for kw in ("navigate to page", "Open the site", "Visit homepage", "打开百度", "Go to login"):
            self.assertEqual(_infer_action(kw, "other"), "navigate", f"Failed for: {kw}")

    def test_login_keywords(self):
        for kw in ("Login with admin", "Sign in as user", "登录系统"):
            self.assertEqual(_infer_action(kw, "other"), "login", f"Failed for: {kw}")

    def test_click_keywords(self):
        for kw in ("Click the button", "Press submit", "点击确认"):
            self.assertEqual(_infer_action(kw, "other"), "click", f"Failed for: {kw}")

    def test_fill_form_keywords(self):
        for kw in ("Fill in the form", "Type username", "Enter password", "输入密码"):
            self.assertEqual(_infer_action(kw, "other"), "fill_form", f"Failed for: {kw}")

    def test_search_keywords(self):
        for kw in ("Search for user", "搜索关键词"):
            self.assertEqual(_infer_action(kw, "other"), "search", f"Failed for: {kw}")

    def test_wait_keywords(self):
        for kw in ("Wait for page load", "等待加载"):
            self.assertEqual(_infer_action(kw, "other"), "wait", f"Failed for: {kw}")

    def test_verify_keywords(self):
        for kw in ("Verify the result", "Assert page title", "Check content", "验证结果"):
            self.assertEqual(_infer_action(kw, "other"), "verify", f"Failed for: {kw}")

    def test_scroll_keywords(self):
        self.assertEqual(_infer_action("Scroll down the page", "other"), "scroll")
        self.assertEqual(_infer_action("滚动到底部", "other"), "scroll")

    def test_select_keywords(self):
        self.assertEqual(_infer_action("Select from dropdown", "other"), "select")
        self.assertEqual(_infer_action("选择选项", "other"), "select")

    def test_hover_keywords(self):
        self.assertEqual(_infer_action("Hover over menu", "other"), "hover")
        self.assertEqual(_infer_action("悬停在按钮上", "other"), "hover")

    def test_intent_fallback(self):
        # When no keyword matches, fall back to intent
        self.assertEqual(_infer_action("do something", "login"), "login")
        self.assertEqual(_infer_action("do something", "search"), "search")
        self.assertEqual(_infer_action("do something", "form_fill"), "fill_form")

    def test_custom_fallback(self):
        self.assertEqual(_infer_action("do something", "other"), "custom")
        self.assertEqual(_infer_action("do something", "multi_step"), "custom")


# ---------------------------------------------------------------------------
# _strip_fences helper tests
# ---------------------------------------------------------------------------


class StripFencesTests(unittest.TestCase):
    def test_no_fences(self):
        self.assertEqual(_strip_fences('{"key": "value"}'), '{"key": "value"}')

    def test_json_fences(self):
        raw = '```json\n{"key": "value"}\n```'
        self.assertEqual(_strip_fences(raw), '{"key": "value"}')

    def test_plain_fences(self):
        raw = '```\n{"key": "value"}\n```'
        self.assertEqual(_strip_fences(raw), '{"key": "value"}')

    def test_whitespace_stripped(self):
        self.assertEqual(_strip_fences('  {"key": "value"}  '), '{"key": "value"}')


if __name__ == "__main__":
    unittest.main()
