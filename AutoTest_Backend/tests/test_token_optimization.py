"""Tests for token consumption optimization.

Validates:
1. estimate_tokens – English, Chinese, mixed, empty, edge cases
2. truncate_to_tokens – within budget, over budget, zero budget, ellipsis
3. allocate_budget – priority ordering, truncation, budget exhaustion
4. WorkingMemory.estimate_tokens – token counting for all fields
5. WorkingMemory.render_for_llm – priority-based budget allocation
6. WorkingMemory._compact – adaptive snippet length, token cap
7. Config setting – AGENT_CONTEXT_MAX_TOKENS default
8. Edge cases – empty memory, huge code, many actions, zero budget
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.services.token_utils import (
    DEFAULT_CONTEXT_MAX_TOKENS,
    _ASCII_CHARS_PER_TOKEN,
    _CJK_CHARS_PER_TOKEN,
    allocate_budget,
    estimate_tokens,
    truncate_to_tokens,
)
from app.services.working_memory import ActionRecord, WorkingMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_analysis(steps: list[str] | None = None):
    """Build a minimal TaskAnalysis-like mock."""
    from app.services.task_analyzer import TaskAnalysis, TargetSite

    return TaskAnalysis(
        intent="search",
        target_site=TargetSite(url="http://example.com", name="example"),
        steps=steps or ["Open page", "Search"],
        success_criteria=["Results visible"],
        complexity="simple",
    )


def _make_execution_plan():
    from app.services.planner import ExecutionPlan, PlanStep

    return ExecutionPlan(
        goal="Open and search",
        steps=[
            PlanStep(step_number=1, action="navigate", description="Open site"),
            PlanStep(step_number=2, action="search", description="Search for item"),
        ],
        estimated_complexity="simple",
    )


# ===========================================================================
# 1. estimate_tokens
# ===========================================================================


class EstimateTokensTests(unittest.TestCase):
    """Validate the heuristic token estimator."""

    def test_empty_string(self):
        self.assertEqual(estimate_tokens(""), 0)

    def test_pure_ascii(self):
        text = "Hello, world!"  # 13 chars
        tokens = estimate_tokens(text)
        # ~13/4 + 1 = 4.25 → 4+1 = 5
        self.assertGreater(tokens, 0)
        self.assertLessEqual(tokens, 10)

    def test_pure_chinese(self):
        text = "你好世界"  # 4 CJK chars
        tokens = estimate_tokens(text)
        # ~4/1.5 + 1 ≈ 3.67 → 3+1=4
        self.assertGreater(tokens, 0)
        self.assertLessEqual(tokens, 8)

    def test_mixed_text(self):
        text = "Hello 你好"  # 6 ASCII + space + 2 CJK
        tokens = estimate_tokens(text)
        self.assertGreater(tokens, 0)

    def test_long_ascii_text(self):
        text = "a" * 4000
        tokens = estimate_tokens(text)
        # ~4000/4 + 1 = 1001
        self.assertGreaterEqual(tokens, 900)
        self.assertLessEqual(tokens, 1200)

    def test_long_chinese_text(self):
        text = "你" * 1500
        tokens = estimate_tokens(text)
        # ~1500/1.5 + 1 = 1001
        self.assertGreaterEqual(tokens, 900)
        self.assertLessEqual(tokens, 1200)

    def test_minimum_one_token(self):
        """Even a single char should estimate at least 1 token."""
        self.assertGreaterEqual(estimate_tokens("x"), 1)

    def test_whitespace_only(self):
        tokens = estimate_tokens("   \n\t")
        self.assertGreaterEqual(tokens, 1)

    def test_code_snippet(self):
        code = 'from selenium import webdriver\ndriver = webdriver.Chrome()\ndriver.get("http://example.com")'
        tokens = estimate_tokens(code)
        self.assertGreater(tokens, 10)
        self.assertLess(tokens, 100)


# ===========================================================================
# 2. truncate_to_tokens
# ===========================================================================


class TruncateToTokensTests(unittest.TestCase):
    """Validate text truncation to a token budget."""

    def test_within_budget_unchanged(self):
        text = "Hello, world!"
        result = truncate_to_tokens(text, 100)
        self.assertEqual(result, text)

    def test_over_budget_truncated(self):
        text = "a" * 10000
        result = truncate_to_tokens(text, 50)
        self.assertLess(len(result), len(text))
        self.assertTrue(result.endswith("…"))

    def test_zero_budget_returns_empty(self):
        self.assertEqual(truncate_to_tokens("Hello", 0), "")

    def test_negative_budget_returns_empty(self):
        self.assertEqual(truncate_to_tokens("Hello", -5), "")

    def test_truncated_result_within_budget(self):
        text = "x" * 5000
        result = truncate_to_tokens(text, 100)
        self.assertLessEqual(estimate_tokens(result), 100)

    def test_chinese_truncation(self):
        text = "你" * 3000
        result = truncate_to_tokens(text, 50)
        self.assertLess(len(result), len(text))
        self.assertTrue(result.endswith("…"))
        self.assertLessEqual(estimate_tokens(result), 50)

    def test_short_text_high_budget(self):
        text = "short"
        result = truncate_to_tokens(text, 10000)
        self.assertEqual(result, text)

    def test_ellipsis_present_on_truncation(self):
        text = "a" * 2000
        result = truncate_to_tokens(text, 10)
        self.assertIn("…", result)


# ===========================================================================
# 3. allocate_budget
# ===========================================================================


class AllocateBudgetTests(unittest.TestCase):
    """Validate priority-based budget allocation."""

    def test_all_fit(self):
        sections = [
            ("a", "hello", 1),
            ("b", "world", 2),
        ]
        result = allocate_budget(sections, 1000)
        labels = [r[0] for r in result]
        self.assertIn("a", labels)
        self.assertIn("b", labels)

    def test_priority_order_preserved(self):
        """Higher priority (lower number) sections are allocated first."""
        sections = [
            ("low", "x" * 2000, 3),
            ("high", "y" * 100, 1),
            ("mid", "z" * 100, 2),
        ]
        result = allocate_budget(sections, 100)
        labels = [r[0] for r in result]
        # "high" should be included; "low" may be dropped
        self.assertIn("high", labels)

    def test_low_priority_dropped_when_budget_tight(self):
        """Low-priority section is dropped when budget is exhausted by higher ones."""
        sections = [
            ("high", "a" * 1000, 1),
            ("low", "b" * 1000, 2),
        ]
        result = allocate_budget(sections, 80)
        labels = [r[0] for r in result]
        self.assertIn("high", labels)
        # low may be truncated or dropped; if present it should be truncated
        if "low" in labels:
            low_text = dict(result)["low"]
            self.assertLess(len(low_text), 1000)

    def test_zero_budget(self):
        sections = [("a", "text", 1)]
        result = allocate_budget(sections, 0)
        self.assertEqual(result, [])

    def test_negative_budget(self):
        sections = [("a", "text", 1)]
        result = allocate_budget(sections, -10)
        self.assertEqual(result, [])

    def test_empty_sections(self):
        result = allocate_budget([], 1000)
        self.assertEqual(result, [])

    def test_truncated_section_included(self):
        """A section that doesn't fully fit is truncated, not dropped."""
        sections = [
            ("big", "a" * 5000, 1),
        ]
        result = allocate_budget(sections, 100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "big")
        self.assertLess(len(result[0][1]), 5000)

    def test_multiple_same_priority(self):
        """Sections with the same priority are all considered."""
        sections = [
            ("a", "short", 1),
            ("b", "also short", 1),
        ]
        result = allocate_budget(sections, 1000)
        self.assertEqual(len(result), 2)


# ===========================================================================
# 4. WorkingMemory.estimate_tokens
# ===========================================================================


class WorkingMemoryTokenEstimateTests(unittest.TestCase):
    """Validate token estimation on WorkingMemory fields."""

    def test_empty_memory(self):
        mem = WorkingMemory(task_prompt="Test task")
        tokens = mem.estimate_tokens()
        self.assertGreater(tokens, 0)

    def test_with_code(self):
        mem = WorkingMemory(task_prompt="Test")
        mem.current_code = "print('hello')\n" * 100
        tokens_with = mem.estimate_tokens()
        mem2 = WorkingMemory(task_prompt="Test")
        tokens_without = mem2.estimate_tokens()
        self.assertGreater(tokens_with, tokens_without)

    def test_with_actions(self):
        mem = WorkingMemory(task_prompt="Test")
        for i in range(5):
            mem.actions.append(ActionRecord(
                step=i,
                thought=f"Thinking about step {i}",
                tool_name="echo",
                observation=f"Result of step {i}" * 20,
            ))
        tokens = mem.estimate_tokens()
        self.assertGreater(tokens, 50)

    def test_with_task_analysis(self):
        mem = WorkingMemory(task_prompt="Test")
        mem.task_analysis = _make_task_analysis()
        tokens_with = mem.estimate_tokens()
        mem2 = WorkingMemory(task_prompt="Test")
        tokens_without = mem2.estimate_tokens()
        self.assertGreater(tokens_with, tokens_without)

    def test_with_execution_plan(self):
        mem = WorkingMemory(task_prompt="Test")
        mem.execution_plan = _make_execution_plan()
        tokens_with = mem.estimate_tokens()
        mem2 = WorkingMemory(task_prompt="Test")
        tokens_without = mem2.estimate_tokens()
        self.assertGreater(tokens_with, tokens_without)

    def test_with_errors(self):
        mem = WorkingMemory(task_prompt="Test")
        for i in range(5):
            mem.accumulated_errors.append(f"Error {i}: something went wrong " * 10)
        tokens = mem.estimate_tokens()
        self.assertGreater(tokens, 30)

    def test_with_knowledge_context(self):
        mem = WorkingMemory(task_prompt="Test")
        mem.knowledge_context = "Some relevant knowledge from the RAG system " * 50
        tokens_with = mem.estimate_tokens()
        mem2 = WorkingMemory(task_prompt="Test")
        tokens_without = mem2.estimate_tokens()
        self.assertGreater(tokens_with, tokens_without)


# ===========================================================================
# 5. WorkingMemory.render_for_llm – priority-based budget
# ===========================================================================


class RenderForLLMPriorityTests(unittest.TestCase):
    """Validate that render_for_llm uses priority-based budget allocation."""

    def test_task_prompt_always_included(self):
        mem = WorkingMemory(task_prompt="My important task")
        rendered = mem.render_for_llm()
        self.assertIn("My important task", rendered)

    def test_task_analysis_included_with_enough_budget(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=2000)
        mem.task_analysis = _make_task_analysis()
        rendered = mem.render_for_llm()
        self.assertIn("Task analysis", rendered)

    def test_execution_plan_included(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=2000)
        mem.execution_plan = _make_execution_plan()
        rendered = mem.render_for_llm()
        self.assertIn("Execution plan", rendered)

    def test_step_results_included(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=2000)
        mem.execution_plan = _make_execution_plan()
        mem.step_results = [
            {"step_number": 1, "status": "completed", "description": "Open site"},
        ]
        rendered = mem.render_for_llm()
        self.assertIn("Plan step results", rendered)
        self.assertIn("[completed]", rendered)

    def test_errors_included(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=2000)
        mem.accumulated_errors = ["TimeoutException at line 23"]
        rendered = mem.render_for_llm()
        self.assertIn("Recent errors", rendered)
        self.assertIn("TimeoutException", rendered)

    def test_code_included(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=2000)
        mem.current_code = "print('hello')"
        rendered = mem.render_for_llm()
        self.assertIn("Current script", rendered)

    def test_knowledge_included(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=2000)
        mem.knowledge_context = "Selenium best practices"
        rendered = mem.render_for_llm()
        self.assertIn("Knowledge context", rendered)

    def test_action_history_included(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=2000)
        mem.actions.append(ActionRecord(step=1, thought="Thinking", tool_name="echo"))
        rendered = mem.render_for_llm()
        self.assertIn("Action history", rendered)

    def test_low_budget_drops_low_priority(self):
        """With a very tight budget, low-priority sections are dropped."""
        mem = WorkingMemory(task_prompt="Test", max_token_budget=20)
        mem.knowledge_context = "Very long knowledge " * 100
        mem.current_code = "Very long code " * 100
        mem.actions.append(ActionRecord(step=1, thought="Thinking" * 50, tool_name="echo"))
        rendered = mem.render_for_llm()
        # Task prompt (P1) should be present
        self.assertIn("Task: Test", rendered)
        # Some lower-priority sections may be dropped or truncated
        tokens = estimate_tokens(rendered)
        # Should be within budget (with some tolerance for assembly overhead)
        self.assertLessEqual(tokens, 30)  # budget=20 + some tolerance

    def test_max_tokens_parameter_overrides_default(self):
        """Passing max_tokens to render_for_llm overrides max_token_budget."""
        mem = WorkingMemory(task_prompt="Test", max_token_budget=50)
        mem.knowledge_context = "Knowledge " * 200
        rendered_default = mem.render_for_llm()
        rendered_large = mem.render_for_llm(max_tokens=5000)
        # With more budget, more content should be included
        self.assertGreaterEqual(len(rendered_large), len(rendered_default))

    def test_render_output_order_deterministic(self):
        """Sections should appear in a deterministic order regardless of priority."""
        mem = WorkingMemory(task_prompt="Test", max_token_budget=5000)
        mem.task_analysis = _make_task_analysis()
        mem.execution_plan = _make_execution_plan()
        mem.accumulated_errors = ["Error 1"]
        mem.current_code = "code()"
        mem.knowledge_context = "knowledge text"
        mem.actions.append(ActionRecord(step=1, thought="Think"))
        rendered = mem.render_for_llm()

        # Find positions — they should follow the defined order
        pos_task = rendered.find("Task:")
        pos_analysis = rendered.find("Task analysis")
        pos_plan = rendered.find("Execution plan")
        pos_knowledge = rendered.find("Knowledge context")
        pos_code = rendered.find("Current script")
        pos_errors = rendered.find("Recent errors")
        pos_history = rendered.find("Action history")

        self.assertLess(pos_task, pos_analysis)
        self.assertLess(pos_analysis, pos_plan)
        self.assertLess(pos_plan, pos_knowledge)
        self.assertLess(pos_knowledge, pos_code)
        self.assertLess(pos_code, pos_errors)
        self.assertLess(pos_errors, pos_history)

    def test_empty_memory_renders(self):
        """WorkingMemory with only task_prompt still renders."""
        mem = WorkingMemory(task_prompt="Just a task")
        rendered = mem.render_for_llm()
        self.assertIn("Just a task", rendered)
        self.assertTrue(len(rendered) > 0)


# ===========================================================================
# 6. WorkingMemory._compact – adaptive summarization
# ===========================================================================


class CompactTests(unittest.TestCase):
    """Validate the enhanced _compact method."""

    def test_compact_triggers_on_overflow(self):
        """Adding more than max_history_steps actions triggers compaction."""
        mem = WorkingMemory(task_prompt="Test", max_history_steps=4)
        for i in range(5):
            mem.add_action(ActionRecord(
                step=i + 1,
                thought=f"Step {i + 1} thought",
                tool_name="echo",
                observation=f"Result {i + 1}",
            ))
        # After compaction, count should be less than 5
        self.assertLess(len(mem.actions), 5)

    def test_compact_preserves_recent_actions(self):
        """After compaction, the most recent actions are preserved."""
        mem = WorkingMemory(task_prompt="Test", max_history_steps=4)
        for i in range(6):
            mem.add_action(ActionRecord(
                step=i + 1,
                thought=f"Step {i + 1}",
                tool_name="tool",
                observation=f"Obs {i + 1}",
            ))
        # The last action should still be present
        last = mem.actions[-1]
        self.assertIn("6", last.thought)

    def test_compact_creates_summary_record(self):
        """Compacted actions are replaced by a summary record at step 0."""
        mem = WorkingMemory(task_prompt="Test", max_history_steps=4)
        for i in range(5):
            mem.add_action(ActionRecord(
                step=i + 1,
                thought=f"Step {i + 1}",
                tool_name="tool",
                observation=f"Obs {i + 1}",
            ))
        # First record should be the summary
        self.assertEqual(mem.actions[0].step, 0)
        self.assertIn("Summary", mem.actions[0].thought)

    def test_compact_summary_token_limited(self):
        """The summary record should not exceed 200 tokens."""
        mem = WorkingMemory(task_prompt="Test", max_history_steps=4)
        for i in range(20):
            mem.add_action(ActionRecord(
                step=i + 1,
                thought=f"Detailed thought for step {i + 1} " * 10,
                tool_name="complex_tool",
                observation=f"Very long observation " * 50,
            ))
        summary = mem.actions[0]
        tokens = estimate_tokens(summary.thought)
        self.assertLessEqual(tokens, 201)  # 200 + 1 for rounding

    def test_compact_many_steps_adaptive_snippet(self):
        """With many compacted steps, snippet lengths are shorter."""
        mem = WorkingMemory(task_prompt="Test", max_history_steps=6)
        for i in range(30):
            mem.add_action(ActionRecord(
                step=i + 1,
                thought=f"Step {i + 1}",
                tool_name="t",
                observation="O" * 200,
            ))
        # Summary should exist and be reasonably short
        summary = mem.actions[0]
        self.assertIn("Summary", summary.thought)
        self.assertLessEqual(estimate_tokens(summary.thought), 201)


# ===========================================================================
# 7. Config setting
# ===========================================================================


class ConfigTests(unittest.TestCase):
    """Validate AGENT_CONTEXT_MAX_TOKENS config."""

    def test_default_value(self):
        self.assertEqual(DEFAULT_CONTEXT_MAX_TOKENS, 4000)

    def test_config_has_setting(self):
        from app.core.config import Settings
        s = Settings(DEEPSEEK_API_KEY="test")
        self.assertEqual(s.AGENT_CONTEXT_MAX_TOKENS, 4000)

    def test_config_custom_value(self):
        from app.core.config import Settings
        s = Settings(DEEPSEEK_API_KEY="test", AGENT_CONTEXT_MAX_TOKENS=8000)
        self.assertEqual(s.AGENT_CONTEXT_MAX_TOKENS, 8000)


# ===========================================================================
# 8. Edge cases
# ===========================================================================


class EdgeCaseTests(unittest.TestCase):
    """Edge case scenarios for token optimization."""

    def test_huge_code_truncated_in_render(self):
        """A very large code block should be truncated by the budget."""
        mem = WorkingMemory(task_prompt="Test", max_token_budget=100)
        mem.current_code = "x = 1\n" * 10000
        rendered = mem.render_for_llm()
        tokens = estimate_tokens(rendered)
        self.assertLessEqual(tokens, 120)  # some tolerance

    def test_huge_knowledge_truncated(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=100)
        mem.knowledge_context = "knowledge " * 5000
        rendered = mem.render_for_llm()
        tokens = estimate_tokens(rendered)
        self.assertLessEqual(tokens, 120)

    def test_many_errors_truncated(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=100)
        for i in range(10):
            mem.record_error(f"Error {i}: " + "detail " * 100)
        rendered = mem.render_for_llm()
        tokens = estimate_tokens(rendered)
        self.assertLessEqual(tokens, 120)

    def test_many_actions_history(self):
        """Many action records should be handled gracefully."""
        mem = WorkingMemory(task_prompt="Test", max_token_budget=200)
        for i in range(50):
            mem.add_action(ActionRecord(
                step=i + 1,
                thought=f"Think {i + 1}",
                tool_name="t",
                observation=f"Obs {i + 1}",
            ))
        rendered = mem.render_for_llm()
        tokens = estimate_tokens(rendered)
        self.assertLessEqual(tokens, 220)

    def test_zero_budget_renders_empty_or_minimal(self):
        mem = WorkingMemory(task_prompt="Test", max_token_budget=0)
        rendered = mem.render_for_llm()
        self.assertEqual(rendered, "")

    def test_render_for_llm_with_none_max_tokens(self):
        """None max_tokens falls back to max_token_budget."""
        mem = WorkingMemory(task_prompt="Test", max_token_budget=100)
        rendered = mem.render_for_llm(max_tokens=None)
        self.assertIn("Test", rendered)

    def test_working_memory_default_budget(self):
        """Default max_token_budget equals DEFAULT_CONTEXT_MAX_TOKENS."""
        mem = WorkingMemory(task_prompt="Test")
        self.assertEqual(mem.max_token_budget, DEFAULT_CONTEXT_MAX_TOKENS)

    def test_render_preserves_existing_fields(self):
        """render_for_llm still includes step_results format from 4.2."""
        mem = WorkingMemory(task_prompt="Test", max_token_budget=5000)
        mem.execution_plan = _make_execution_plan()
        mem.step_results = [
            {"step_number": 1, "status": "completed", "description": "Open site"},
            {"step_number": 2, "status": "failed", "description": "Login attempt"},
        ]
        rendered = mem.render_for_llm()
        self.assertIn("Step 1: [completed]", rendered)
        self.assertIn("Step 2: [failed]", rendered)

    def test_to_dict_unchanged(self):
        """to_dict should still work correctly after token optimization changes."""
        mem = WorkingMemory(task_prompt="Test")
        mem.execution_plan = _make_execution_plan()
        mem.step_results = [{"step_number": 1, "status": "completed", "description": "Done"}]
        mem.current_code = "print('hi')"
        d = mem.to_dict()
        self.assertEqual(d["task_prompt"], "Test")
        self.assertIsNotNone(d["execution_plan"])
        self.assertEqual(len(d["step_results"]), 1)
        self.assertEqual(d["current_code_lines"], 1)


# ===========================================================================
# 9. Regression: existing tests should still pass patterns
# ===========================================================================


class RegressionTests(unittest.TestCase):
    """Ensure the refactored render_for_llm preserves the same content patterns
    as the original implementation when budget is generous."""

    def test_render_includes_all_sections_with_large_budget(self):
        """With a large budget all sections should appear."""
        mem = WorkingMemory(task_prompt="Test task", max_token_budget=10000)
        mem.task_analysis = _make_task_analysis()
        mem.execution_plan = _make_execution_plan()
        mem.step_results = [
            {"step_number": 1, "status": "completed", "description": "Open site"},
        ]
        mem.knowledge_context = "Selenium docs"
        mem.current_code = "driver.get('http://example.com')"
        mem.accumulated_errors = ["Error: timeout"]
        mem.actions.append(ActionRecord(
            step=1,
            thought="Thinking about navigation",
            tool_name="generate_selenium_script",
            observation="Script generated successfully",
        ))

        rendered = mem.render_for_llm()
        self.assertIn("Task: Test task", rendered)
        self.assertIn("Task analysis", rendered)
        self.assertIn("Execution plan", rendered)
        self.assertIn("Plan step results", rendered)
        self.assertIn("Knowledge context", rendered)
        self.assertIn("Current script", rendered)
        self.assertIn("Recent errors", rendered)
        self.assertIn("Action history", rendered)

    def test_render_without_optional_fields(self):
        """With no optional fields, only task prompt appears."""
        mem = WorkingMemory(task_prompt="Simple task", max_token_budget=10000)
        rendered = mem.render_for_llm()
        self.assertIn("Task: Simple task", rendered)
        self.assertNotIn("Task analysis", rendered)
        self.assertNotIn("Execution plan", rendered)
        self.assertNotIn("Knowledge context", rendered)
        self.assertNotIn("Current script", rendered)
        self.assertNotIn("Recent errors", rendered)
        self.assertNotIn("Action history", rendered)


if __name__ == "__main__":
    unittest.main()
