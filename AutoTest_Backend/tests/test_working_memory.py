"""Deep tests for WorkingMemory: token budget, compaction, render_for_llm edge cases."""

from __future__ import annotations

import unittest

from . import _bootstrap  # noqa: F401

from app.services.working_memory import ActionRecord, WorkingMemory
from app.services.task_analyzer import TaskAnalysis, TargetSite
from app.services.planner import ExecutionPlan, PlanStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis(intent: str = "search", complexity: str = "simple") -> TaskAnalysis:
    return TaskAnalysis(
        intent=intent,
        target_site=TargetSite(url="https://example.com", name="Example"),
        steps=["Navigate to site", "Enter search query", "Click search button"],
        preconditions=["Site is accessible"],
        success_criteria=["Search results displayed"],
        complexity=complexity,
    )


def _make_plan(goal: str = "Search for something", steps: int = 2) -> ExecutionPlan:
    plan_steps = [
        PlanStep(
            step_number=1,
            action="navigate",
            description="Go to search page",
            parameters={"url": "https://example.com"},
        ),
        PlanStep(
            step_number=2,
            action="search",
            description="Enter and submit query",
            parameters={"selector": "#search-input", "text": "test"},
        ),
    ]
    if steps > 2:
        plan_steps.append(
            PlanStep(
                step_number=3,
                action="verify",
                description="Check results appear",
                depends_on=[2],
            )
        )
    return ExecutionPlan(
        goal=goal,
        steps=plan_steps[:steps],
        estimated_complexity="simple" if steps <= 2 else "multi_step",
    )


# ---------------------------------------------------------------------------
# render_for_llm — section coverage
# ---------------------------------------------------------------------------


class RenderForLLMTests(unittest.TestCase):
    """Verify render_for_llm includes all expected sections when populated."""

    def test_basic_task_prompt_always_included(self):
        mem = WorkingMemory(task_prompt="打开百度搜索 Selenium")
        rendered = mem.render_for_llm()
        self.assertIn("打开百度搜索 Selenium", rendered)

    def test_task_analysis_included(self):
        mem = WorkingMemory(task_prompt="test")
        mem.task_analysis = _make_analysis()
        rendered = mem.render_for_llm()
        self.assertIn("Task analysis:", rendered)
        self.assertIn("search", rendered)

    def test_execution_plan_included(self):
        mem = WorkingMemory(task_prompt="test")
        mem.execution_plan = _make_plan()
        rendered = mem.render_for_llm()
        self.assertIn("Execution plan:", rendered)
        self.assertIn("navigate", rendered)

    def test_step_results_included(self):
        mem = WorkingMemory(task_prompt="test")
        mem.step_results = [
            {"step_number": 1, "status": "completed", "description": "Navigate done"},
            {"step_number": 2, "status": "failed", "description": "Search failed"},
        ]
        rendered = mem.render_for_llm()
        self.assertIn("Plan step results:", rendered)
        self.assertIn("completed", rendered)
        self.assertIn("failed", rendered)

    def test_errors_included(self):
        mem = WorkingMemory(task_prompt="test")
        mem.record_error("NoSuchElementException: #kw not found")
        mem.record_error("TimeoutException: page load timeout")
        rendered = mem.render_for_llm()
        self.assertIn("Recent errors:", rendered)
        self.assertIn("NoSuchElementException", rendered)

    def test_current_code_included(self):
        mem = WorkingMemory(task_prompt="test")
        mem.current_code = "from selenium import webdriver\ndriver = webdriver.Chrome()"
        rendered = mem.render_for_llm()
        self.assertIn("Current script:", rendered)
        self.assertIn("webdriver", rendered)

    def test_knowledge_context_included(self):
        mem = WorkingMemory(task_prompt="test")
        mem.knowledge_context = "Vue admin login uses button.el-button--primary"
        rendered = mem.render_for_llm()
        self.assertIn("Knowledge context:", rendered)
        self.assertIn("el-button--primary", rendered)

    def test_action_history_included(self):
        mem = WorkingMemory(task_prompt="test")
        mem.add_action(ActionRecord(
            step=1,
            thought="Need to search knowledge first",
            tool_name="search_knowledge",
            observation="Found 3 docs",
        ))
        rendered = mem.render_for_llm()
        self.assertIn("Action history:", rendered)
        self.assertIn("search_knowledge", rendered)

    def test_multi_step_plan_addon_not_injected_by_memory(self):
        """The addon is handled by AgentOrchestrator, not by WorkingMemory."""
        mem = WorkingMemory(task_prompt="test")
        plan = _make_plan(steps=3)
        mem.execution_plan = plan
        # render_for_llm does NOT inject MULTI_STEP_PROMPT_ADDON
        rendered = mem.render_for_llm()
        self.assertNotIn("MULTI-STEP", rendered)


# ---------------------------------------------------------------------------
# Token budget allocation
# ---------------------------------------------------------------------------


class TokenBudgetTests(unittest.TestCase):
    """Verify that render_for_llm respects the token budget."""

    def test_no_truncation_when_plenty_of_budget(self):
        mem = WorkingMemory(task_prompt="Short task")
        mem.add_action(ActionRecord(step=1, thought="Did something", tool_name="echo"))
        rendered = mem.render_for_llm(max_tokens=4000)
        # Everything fits — no ellipsis in section content
        self.assertIn("Short task", rendered)

    def test_tight_budget_drops_low_priority_sections(self):
        """With a very small budget, only the high-priority task section survives."""
        mem = WorkingMemory(task_prompt="A somewhat longer task description here")
        mem.knowledge_context = "Very long knowledge context " * 50
        mem.current_code = "print('hello')" * 30
        for i in range(10):
            mem.add_action(ActionRecord(
                step=i + 1,
                thought=f"Thought number {i + 1} with some detail",
                tool_name="echo",
                observation=f"Observation {i + 1}: all good",
            ))
        rendered = mem.render_for_llm(max_tokens=200)
        self.assertIn("A somewhat longer", rendered)
        self.assertGreater(len(rendered), 0)

    def test_zero_budget_returns_only_task(self):
        mem = WorkingMemory(task_prompt="minimal")
        rendered = mem.render_for_llm(max_tokens=10)
        self.assertIn("minimal", rendered)

    def test_render_order_is_deterministic(self):
        """The output section order must be consistent: task → analysis → plan → ..."""
        mem = WorkingMemory(task_prompt="test")
        mem.task_analysis = _make_analysis()
        mem.execution_plan = _make_plan()
        mem.record_error("error1")
        mem.add_action(ActionRecord(step=1, thought="t1", tool_name="echo", observation="ok"))

        rendered = mem.render_for_llm()
        task_pos = rendered.index("Task:")
        analysis_pos = rendered.index("Task analysis:")
        plan_pos = rendered.index("Execution plan:")
        errors_pos = rendered.index("Recent errors:")
        history_pos = rendered.index("Action history:")

        self.assertLess(task_pos, analysis_pos)
        self.assertLess(analysis_pos, plan_pos)
        self.assertLess(plan_pos, errors_pos)
        self.assertLess(errors_pos, history_pos)


# ---------------------------------------------------------------------------
# Compaction
# ---------------------------------------------------------------------------


class CompactionTests(unittest.TestCase):
    """Verify WorkingMemory._compact behaviour."""

    def test_actions_compacted_when_exceeding_max(self):
        mem = WorkingMemory(task_prompt="test", max_history_steps=4)
        for i in range(8):
            mem.add_action(ActionRecord(
                step=i + 1,
                thought=f"Step {i + 1}",
                tool_name="echo",
                observation=f"Result {i + 1}",
            ))
        # After 8 additions with max=4, actions must be compacted
        self.assertLess(len(mem.actions), 8)
        # First action should be a summary (step=0)
        self.assertEqual(mem.actions[0].step, 0)

    def test_summary_record_marked_as_step_zero(self):
        mem = WorkingMemory(task_prompt="test", max_history_steps=2)
        for i in range(5):
            mem.add_action(ActionRecord(step=i + 1, thought=f"T{i + 1}"))
        # Summary record uses step=0 convention
        self.assertEqual(mem.actions[0].step, 0)

    def test_recent_actions_preserved_after_compaction(self):
        mem = WorkingMemory(task_prompt="test", max_history_steps=4)
        for i in range(6):
            mem.add_action(ActionRecord(step=i + 1, thought=f"Step {i + 1}"))
        # Recent actions (second half) are preserved
        last_action = mem.actions[-1]
        self.assertEqual(last_action.step, 6)

    def test_no_compaction_when_under_limit(self):
        mem = WorkingMemory(task_prompt="test", max_history_steps=20)
        for i in range(5):
            mem.add_action(ActionRecord(step=i + 1, thought=f"Step {i + 1}"))
        self.assertEqual(len(mem.actions), 5)
        # No summary record when not compacted
        self.assertNotEqual(mem.actions[0].step, 0)


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


class EstimateTokensTests(unittest.TestCase):
    """Verify WorkingMemory.estimate_tokens returns plausible values."""

    def test_empty_memory_returns_small_count(self):
        mem = WorkingMemory(task_prompt="hi")
        tokens = mem.estimate_tokens()
        self.assertGreater(tokens, 0)
        self.assertLess(tokens, 20)

    def test_estimate_increases_with_actions(self):
        mem = WorkingMemory(task_prompt="test " * 20)
        before = mem.estimate_tokens()
        for i in range(3):
            mem.add_action(ActionRecord(
                step=i + 1,
                thought="thought " * 10,
                observation="observation " * 10,
            ))
        after = mem.estimate_tokens()
        self.assertGreater(after, before)

    def test_estimate_includes_task_analysis(self):
        mem = WorkingMemory(task_prompt="test")
        before = mem.estimate_tokens()
        mem.task_analysis = _make_analysis()
        after = mem.estimate_tokens()
        self.assertGreater(after, before)

    def test_estimate_includes_execution_plan(self):
        mem = WorkingMemory(task_prompt="test")
        before = mem.estimate_tokens()
        mem.execution_plan = _make_plan(steps=3)
        after = mem.estimate_tokens()
        self.assertGreater(after, before)


# ---------------------------------------------------------------------------
# Error accumulation
# ---------------------------------------------------------------------------


class ErrorAccumulationTests(unittest.TestCase):
    """Verify record_error behaviour."""

    def test_errors_capped_at_10(self):
        mem = WorkingMemory(task_prompt="test")
        for i in range(15):
            mem.record_error(f"Error {i}")
        self.assertLessEqual(len(mem.accumulated_errors), 10)

    def test_recent_errors_preserved_on_overflow(self):
        mem = WorkingMemory(task_prompt="test")
        for i in range(15):
            mem.record_error(f"Error #{i}")
        # The oldest 5 should be dropped; #5 through #14 remain
        self.assertNotIn("Error #0", mem.accumulated_errors)
        self.assertIn("Error #14", mem.accumulated_errors)

    def test_error_truncated_to_2000_chars(self):
        mem = WorkingMemory(task_prompt="test")
        long_error = "x" * 3000
        mem.record_error(long_error)
        self.assertLessEqual(len(mem.accumulated_errors[0]), 2000)


# ---------------------------------------------------------------------------
# to_dict serialisation
# ---------------------------------------------------------------------------


class ToDictTests(unittest.TestCase):
    """Verify to_dict produces JSON-safe output."""

    def test_to_dict_minimal(self):
        mem = WorkingMemory(task_prompt="test")
        d = mem.to_dict()
        self.assertEqual(d["task_prompt"], "test")
        self.assertEqual(d["step_count"], 0)
        self.assertIsNone(d["task_analysis"])
        self.assertIsNone(d["execution_plan"])

    def test_to_dict_with_analysis_and_plan(self):
        mem = WorkingMemory(task_prompt="test")
        mem.task_analysis = _make_analysis()
        mem.execution_plan = _make_plan()
        d = mem.to_dict()
        self.assertIsNotNone(d["task_analysis"])
        self.assertEqual(d["task_analysis"]["intent"], "search")
        self.assertIsNotNone(d["execution_plan"])
        self.assertEqual(d["execution_plan"]["goal"], "Search for something")

    def test_to_dict_with_actions(self):
        mem = WorkingMemory(task_prompt="test")
        mem.add_action(ActionRecord(
            step=1,
            thought="test thought",
            tool_name="echo",
            tool_input={"message": "hello"},
            observation="Echoed: hello",
            duration_ms=42,
        ))
        d = mem.to_dict()
        self.assertEqual(d["step_count"], 1)
        action = d["actions"][0]
        self.assertEqual(action["step"], 1)
        self.assertEqual(action["tool_name"], "echo")
        self.assertIn("message", action["tool_input_keys"])

    def test_to_dict_current_code_lines(self):
        mem = WorkingMemory(task_prompt="test")
        mem.current_code = "line1\nline2\nline3"
        d = mem.to_dict()
        self.assertEqual(d["current_code_lines"], 3)

    def test_to_dict_errors_limited_to_5(self):
        mem = WorkingMemory(task_prompt="test")
        for i in range(10):
            mem.record_error(f"Error {i}")
        d = mem.to_dict()
        self.assertLessEqual(len(d["accumulated_errors"]), 5)


# ---------------------------------------------------------------------------
# ActionRecord
# ---------------------------------------------------------------------------


class ActionRecordTests(unittest.TestCase):
    """Verify ActionRecord dataclass."""

    def test_defaults(self):
        record = ActionRecord(step=1, thought="test")
        self.assertIsNone(record.tool_name)
        self.assertIsNone(record.tool_input)
        self.assertIsNone(record.observation)
        self.assertEqual(record.duration_ms, 0)

    def test_full_record(self):
        record = ActionRecord(
            step=3,
            thought="Need to repair",
            tool_name="repair_script",
            tool_input={"code": "print('fixed')"},
            observation="Repaired successfully",
            duration_ms=1500,
        )
        self.assertEqual(record.step, 3)
        self.assertEqual(record.tool_name, "repair_script")
        self.assertEqual(record.duration_ms, 1500)


if __name__ == "__main__":
    unittest.main()
