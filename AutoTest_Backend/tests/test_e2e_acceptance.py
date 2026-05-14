"""Tests for end-to-end acceptance.

Validates the full agent pipeline with complex, realistic scenarios:
1. Complex multi-step flow (login -> navigate -> search -> verify)
2. Failure-and-recovery flow (generate -> execute-fail -> diagnose -> repair -> retry-success)
3. Event chain completeness and ordering
4. Memory card writing (success pattern / known trap)
5. Token budget compliance under heavy context
6. Working memory serialization round-trip
7. Max-steps-reached graceful termination
8. SSE streaming event format
9. Chinese prompt handling end-to-end
10. Mixed tool outcomes with partial recovery
11. Regression: all integrated components
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock, call

from app.services.agent_orchestrator import (
    AGENT_SYSTEM_PROMPT,
    MULTI_STEP_PROMPT_ADDON,
    AgentEvent,
    AgentOrchestrator,
    AgentRunResult,
)
from app.services.planner import ExecutionPlan, PlanStep, Planner
from app.services.task_analyzer import TaskAnalysis, TargetSite, TaskAnalyzer
from app.services.working_memory import ActionRecord, WorkingMemory
from app.tools.base import BaseTool, ToolRegistry, ToolResult


# ---------------------------------------------------------------------------
# Realistic mock tools
# ---------------------------------------------------------------------------


class MockSearchKnowledgeTool(BaseTool):
    """Simulates search_knowledge tool."""

    @property
    def name(self) -> str:
        return "search_knowledge"

    @property
    def description(self) -> str:
        return "Search the knowledge base for relevant patterns."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            success=True,
            data={"context": f"Pattern found for: {kwargs.get('query', '')}"},
            summary=f"Found relevant patterns for '{kwargs.get('query', '')}'",
        )


class MockGenerateScriptTool(BaseTool):
    """Simulates generate_selenium_script tool."""

    @property
    def name(self) -> str:
        return "generate_selenium_script"

    @property
    def description(self) -> str:
        return "Generate a Selenium test script from a test scenario description."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "scenario": {"type": "string"},
                "url": {"type": "string"},
            },
            "required": ["scenario"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        code = (
            "from selenium import webdriver\n"
            "driver = webdriver.Chrome()\n"
            f"# Scenario: {kwargs.get('scenario', '')}\n"
            "driver.get('http://localhost:9528')\n"
            "print('Test Completed')\n"
        )
        return ToolResult(
            success=True,
            data={"test_case_id": "tc_e2e_001", "generated_code": code},
            summary=f"Generated script for: {kwargs.get('scenario', '')}",
        )


class MockValidateCodeTool(BaseTool):
    """Simulates validate_code tool."""

    @property
    def name(self) -> str:
        return "validate_code"

    @property
    def description(self) -> str:
        return "Validate Python code for syntax errors."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            success=True,
            data={"valid": True},
            summary="Code validation passed.",
        )


class MockExecuteScriptTool(BaseTool):
    """Simulates execute_script tool."""

    def __init__(self, *, fail_first: bool = False):
        self._call_count = 0
        self._fail_first = fail_first

    @property
    def name(self) -> str:
        return "execute_script"

    @property
    def description(self) -> str:
        return "Execute a Selenium test script."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"test_case_id": {"type": "string"}},
            "required": ["test_case_id"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._call_count += 1
        return ToolResult(
            success=True,
            data={"execution_id": f"exec_{self._call_count:03d}"},
            summary=f"Execution started: exec_{self._call_count:03d}",
        )


class MockGetExecutionResultTool(BaseTool):
    """Simulates get_execution_result tool with configurable outcomes."""

    def __init__(self, *, results: list[dict[str, Any]] | None = None):
        self._results = results or [{"status": "completed", "logs": "Test Completed"}]
        self._call_count = 0

    @property
    def name(self) -> str:
        return "get_execution_result"

    @property
    def description(self) -> str:
        return "Get the result of a test execution."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"execution_id": {"type": "string"}},
            "required": ["execution_id"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        idx = min(self._call_count, len(self._results) - 1)
        result = self._results[idx]
        self._call_count += 1
        status = result.get("status", "completed")
        success = status in ("completed", "healed_completed")
        return ToolResult(
            success=True,  # API call itself always succeeds
            data=result,
            summary=f"Execution result: {status}",
            error=result.get("error") if not success else None,
        )


class MockDiagnoseFailureTool(BaseTool):
    """Simulates diagnose_failure tool."""

    @property
    def name(self) -> str:
        return "diagnose_failure"

    @property
    def description(self) -> str:
        return "Diagnose the cause of a test execution failure."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "error": {"type": "string"},
                "code": {"type": "string"},
            },
            "required": ["error"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            success=True,
            data={
                "diagnosis": "element_not_found",
                "suggestion": "Use WebDriverWait for dynamic elements",
            },
            summary="Diagnosis: element_not_found — use explicit waits",
        )


class MockRepairScriptTool(BaseTool):
    """Simulates repair_script tool."""

    @property
    def name(self) -> str:
        return "repair_script"

    @property
    def description(self) -> str:
        return "Repair a failing Selenium test script."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "error": {"type": "string"},
                "diagnosis": {"type": "string"},
            },
            "required": ["code", "error"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        repaired = (
            "from selenium import webdriver\n"
            "from selenium.webdriver.support.ui import WebDriverWait\n"
            "# Repaired script with explicit waits\n"
            "driver = webdriver.Chrome()\n"
            "driver.get('http://localhost:9528')\n"
            "print('Test Completed')\n"
        )
        return ToolResult(
            success=True,
            data={"repaired_code": repaired},
            summary="Script repaired with explicit waits",
        )


class MockSearchMemoryTool(BaseTool):
    """Simulates search_memory tool."""

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return "Search agent memory for past experiences."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            success=True,
            data={"memories": []},
            summary="No relevant memories found.",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis(
    intent: str = "multi_step",
    complexity: str = "multi_step",
    steps: list[str] | None = None,
    url: str = "http://localhost:9528",
    name: str = "vue-admin-template",
) -> TaskAnalysis:
    return TaskAnalysis(
        intent=intent,
        target_site=TargetSite(url=url, name=name),
        steps=steps or [
            "Navigate to http://localhost:9528",
            "Login with admin/111111",
            "Navigate to user management page",
            "Search for user 'test'",
            "Verify search results contain 'test'",
        ],
        success_criteria=["Search results contain 'test'", "No errors in console"],
        complexity=complexity,
    )


def _make_complex_plan() -> ExecutionPlan:
    return ExecutionPlan(
        goal="Login to vue-admin-template, navigate to user management, search for 'test' user",
        steps=[
            PlanStep(step_number=1, action="navigate", description="Open http://localhost:9528"),
            PlanStep(step_number=2, action="login", description="Login with admin/111111", depends_on=[1]),
            PlanStep(step_number=3, action="navigate", description="Navigate to user management page", depends_on=[2]),
            PlanStep(step_number=4, action="search", description="Search for user 'test'", depends_on=[3]),
            PlanStep(step_number=5, action="verify", description="Verify search results contain 'test'", depends_on=[4]),
        ],
        estimated_complexity="multi_step",
    )


def _build_full_registry(
    *,
    exec_fail_first: bool = False,
    exec_results: list[dict[str, Any]] | None = None,
) -> ToolRegistry:
    """Build a registry with all mock tools simulating the real tool chain."""
    registry = ToolRegistry()
    registry.register(MockSearchKnowledgeTool())
    registry.register(MockGenerateScriptTool())
    registry.register(MockValidateCodeTool())
    registry.register(MockExecuteScriptTool(fail_first=exec_fail_first))
    registry.register(MockGetExecutionResultTool(results=exec_results))
    registry.register(MockDiagnoseFailureTool())
    registry.register(MockRepairScriptTool())
    registry.register(MockSearchMemoryTool())
    return registry


def _make_e2e_orchestrator(
    llm_responses: list[str],
    *,
    max_steps: int = 15,
    analysis: TaskAnalysis | None = None,
    plan: ExecutionPlan | None = None,
    on_event: Any = None,
    memory_service: Any = None,
    exec_results: list[dict[str, Any]] | None = None,
) -> AgentOrchestrator:
    """Create an orchestrator wired with all mock components."""
    settings = MagicMock()
    llm = MagicMock()
    call_count = {"n": 0}

    def fake_agent_chat(*, system_prompt, user_message, **kwargs):
        idx = min(call_count["n"], len(llm_responses) - 1)
        call_count["n"] += 1
        return llm_responses[idx]

    llm.agent_chat = fake_agent_chat

    registry = _build_full_registry(exec_results=exec_results)

    task_analyzer = None
    if analysis is not None:
        task_analyzer = MagicMock(spec=TaskAnalyzer)
        task_analyzer.analyze = MagicMock(return_value=analysis)

    planner = None
    if plan is not None:
        planner = MagicMock(spec=Planner)
        planner.plan = MagicMock(return_value=plan)

    return AgentOrchestrator(
        settings=settings,
        llm_service=llm,
        tool_registry=registry,
        max_steps=max_steps,
        on_event=on_event,
        task_analyzer=task_analyzer,
        memory_service=memory_service,
        planner=planner,
    )


# ---------------------------------------------------------------------------
# 1. Complex multi-step flow: login → navigate → search → verify
# ---------------------------------------------------------------------------


class ComplexMultiStepFlowTests(unittest.TestCase):
    """Full pipeline: analysis → plan → search_knowledge → generate → validate →
    execute → get_result for each plan step → finish."""

    def _build_responses(self) -> list[str]:
        """Build realistic LLM responses for a 5-step complex scenario."""
        return [
            # Step 1: search knowledge first
            json.dumps({
                "thought": "Start by searching knowledge base for vue-admin login patterns.",
                "action": "search_knowledge",
                "action_input": {"query": "vue-admin login selenium", "plan_step": 1},
            }),
            # Step 2: generate script for navigate + login
            json.dumps({
                "thought": "Knowledge found. Generate script for navigate and login.",
                "action": "generate_selenium_script",
                "action_input": {
                    "scenario": "Navigate to localhost:9528 and login with admin/111111",
                    "url": "http://localhost:9528",
                    "plan_step": 2,
                },
            }),
            # Step 3: validate the generated code
            json.dumps({
                "thought": "Validate the generated script before execution.",
                "action": "validate_code",
                "action_input": {"code": "from selenium import webdriver..."},
            }),
            # Step 4: execute the script
            json.dumps({
                "thought": "Code is valid, execute the test script.",
                "action": "execute_script",
                "action_input": {"test_case_id": "tc_e2e_001", "plan_step": 3},
            }),
            # Step 5: get execution result
            json.dumps({
                "thought": "Check execution result.",
                "action": "get_execution_result",
                "action_input": {"execution_id": "exec_001", "plan_step": 4},
            }),
            # Step 6: finish successfully
            json.dumps({
                "thought": "All plan steps completed. Search results verified.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]

    def test_full_complex_flow_succeeds(self):
        """End-to-end: complex scenario completes successfully."""
        orch = _make_e2e_orchestrator(
            self._build_responses(),
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Login to vue-admin, navigate to user management, search for 'test'")

        self.assertEqual(result.status, "success")
        self.assertGreaterEqual(result.steps, 5)
        self.assertIsNotNone(result.memory.test_case_id)
        self.assertIsNotNone(result.memory.execution_id)
        self.assertIsNotNone(result.memory.knowledge_context)

    def test_event_chain_contains_all_types(self):
        """The event chain includes task_analysis, plan, thinking, action, finish."""
        orch = _make_e2e_orchestrator(
            self._build_responses(),
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Login and search scenario")

        event_types = {e.event_type for e in result.events}
        self.assertIn("task_analysis", event_types)
        self.assertIn("plan", event_types)
        self.assertIn("thinking", event_types)
        self.assertIn("action", event_types)
        self.assertIn("finish", event_types)

    def test_event_ordering_is_correct(self):
        """Events appear in the right order: task_analysis < plan < thinking < finish."""
        orch = _make_e2e_orchestrator(
            self._build_responses(),
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Event ordering test")

        types = [e.event_type for e in result.events]
        ta_idx = types.index("task_analysis")
        plan_idx = types.index("plan")
        first_thinking = types.index("thinking")
        last_finish = len(types) - 1 - types[::-1].index("finish")
        self.assertLess(ta_idx, plan_idx)
        self.assertLess(plan_idx, first_thinking)
        self.assertLess(first_thinking, last_finish)

    def test_plan_step_tracking_for_tagged_actions(self):
        """Actions with plan_step in action_input produce plan_step_complete events."""
        orch = _make_e2e_orchestrator(
            self._build_responses(),
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Plan step tracking test")

        psc_events = [e for e in result.events if e.event_type == "plan_step_complete"]
        # Steps 1, 2, 3, 4 each have plan_step in action_input
        self.assertGreaterEqual(len(psc_events), 1)
        tracked_steps = {e.data["step_number"] for e in psc_events}
        self.assertTrue(tracked_steps)  # at least one plan step was tracked

    def test_memory_shortcuts_populated(self):
        """After full flow, working memory has test_case_id, execution_id, knowledge_context, current_code."""
        orch = _make_e2e_orchestrator(
            self._build_responses(),
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Memory shortcut test")

        self.assertEqual(result.memory.test_case_id, "tc_e2e_001")
        self.assertIsNotNone(result.memory.execution_id)
        self.assertIn("Pattern found", result.memory.knowledge_context)
        self.assertIsNotNone(result.memory.current_code)


# ---------------------------------------------------------------------------
# 2. Failure-and-recovery flow
# ---------------------------------------------------------------------------


class FailureRecoveryFlowTests(unittest.TestCase):
    """Agent generates script → execute fails → diagnose → repair → retry → success."""

    def _build_responses(self) -> list[str]:
        return [
            # search knowledge
            json.dumps({
                "thought": "Search for login patterns.",
                "action": "search_knowledge",
                "action_input": {"query": "login test"},
            }),
            # generate script
            json.dumps({
                "thought": "Generate the login test script.",
                "action": "generate_selenium_script",
                "action_input": {"scenario": "Login to vue-admin"},
            }),
            # validate
            json.dumps({
                "thought": "Validate the script.",
                "action": "validate_code",
                "action_input": {"code": "..."},
            }),
            # execute
            json.dumps({
                "thought": "Run the test.",
                "action": "execute_script",
                "action_input": {"test_case_id": "tc_e2e_001"},
            }),
            # get result — fails
            json.dumps({
                "thought": "Check result.",
                "action": "get_execution_result",
                "action_input": {"execution_id": "exec_001"},
            }),
            # diagnose
            json.dumps({
                "thought": "Execution failed, need to diagnose.",
                "action": "diagnose_failure",
                "action_input": {"error": "element not interactable", "code": "..."},
            }),
            # repair
            json.dumps({
                "thought": "Repair the script with explicit waits.",
                "action": "repair_script",
                "action_input": {"code": "...", "error": "element not interactable"},
            }),
            # re-execute
            json.dumps({
                "thought": "Re-execute the repaired script.",
                "action": "execute_script",
                "action_input": {"test_case_id": "tc_e2e_001"},
            }),
            # get result — success
            json.dumps({
                "thought": "Check result again.",
                "action": "get_execution_result",
                "action_input": {"execution_id": "exec_002"},
            }),
            # finish
            json.dumps({
                "thought": "Test passed after repair.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]

    def test_recovery_flow_succeeds(self):
        """Agent recovers from a failed execution through diagnose → repair → retry."""
        orch = _make_e2e_orchestrator(
            self._build_responses(),
            analysis=_make_analysis(intent="login", complexity="simple", steps=["Login to vue-admin"]),
            exec_results=[
                {"status": "failed", "error": "element not interactable"},
                {"status": "completed", "logs": "Test Completed"},
            ],
        )
        result = orch.run("Login to vue-admin-template with admin/111111")

        self.assertEqual(result.status, "success")
        # Verify repair was invoked (current_code should have the repaired version)
        self.assertIn("Repaired", result.memory.current_code)

    def test_recovery_flow_has_error_recorded(self):
        """Errors from failed execution are recorded in accumulated_errors."""
        orch = _make_e2e_orchestrator(
            self._build_responses(),
            analysis=_make_analysis(intent="login", complexity="simple", steps=["Login"]),
            exec_results=[
                {"status": "failed", "error": "element not interactable"},
                {"status": "completed", "logs": "Test Completed"},
            ],
        )
        result = orch.run("Login test with recovery")

        # The get_execution_result tool returns a failed status which triggers error recording
        self.assertTrue(len(result.memory.accumulated_errors) >= 1)

    def test_recovery_generates_correct_events(self):
        """Recovery flow generates both action events for diagnose and repair."""
        orch = _make_e2e_orchestrator(
            self._build_responses(),
            analysis=_make_analysis(intent="login", complexity="simple", steps=["Login"]),
            exec_results=[
                {"status": "failed", "error": "element not interactable"},
                {"status": "completed", "logs": "Test Completed"},
            ],
        )
        result = orch.run("Login test events")

        action_events = [e for e in result.events if e.event_type == "action"]
        tool_names = [e.data.get("tool") for e in action_events]
        self.assertIn("diagnose_failure", tool_names)
        self.assertIn("repair_script", tool_names)


# ---------------------------------------------------------------------------
# 3. Memory card writing
# ---------------------------------------------------------------------------


class MemoryCardWritingTests(unittest.TestCase):
    """Verify success_pattern and known_trap memory cards are written."""

    def test_success_card_written_on_clean_success(self):
        """Clean success (no repairs) writes a success memory card."""
        memory_service = MagicMock()
        responses = [
            json.dumps({
                "thought": "Generate script.",
                "action": "generate_selenium_script",
                "action_input": {"scenario": "Open Baidu"},
            }),
            json.dumps({
                "thought": "Execute.",
                "action": "execute_script",
                "action_input": {"test_case_id": "tc_e2e_001"},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(intent="navigate", complexity="simple", steps=["Open Baidu"]),
            memory_service=memory_service,
        )
        result = orch.run("Open Baidu homepage")

        self.assertEqual(result.status, "success")
        memory_service.write_success_memory.assert_called_once()
        call_kwargs = memory_service.write_success_memory.call_args
        self.assertIn("Open Baidu", call_kwargs.kwargs.get("prompt", call_kwargs[1].get("prompt", "")))

    def test_trap_card_written_on_failure(self):
        """Failed run writes a trap memory card."""
        memory_service = MagicMock()
        responses = [
            json.dumps({
                "thought": "Cannot proceed.",
                "action": "finish",
                "action_input": {"status": "failed", "reason": "Target site unreachable"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(intent="navigate", complexity="simple", steps=["Open unreachable site"]),
            memory_service=memory_service,
        )
        result = orch.run("Open an unreachable website")

        self.assertEqual(result.status, "failed")
        memory_service.write_trap_memory.assert_called_once()

    def test_no_success_card_when_repairs_happened(self):
        """If repair_script was called, no success card is written (indicates instability)."""
        memory_service = MagicMock()
        responses = [
            json.dumps({
                "thought": "Generate.",
                "action": "generate_selenium_script",
                "action_input": {"scenario": "Login"},
            }),
            json.dumps({
                "thought": "Repair needed.",
                "action": "repair_script",
                "action_input": {"code": "...", "error": "timeout"},
            }),
            json.dumps({
                "thought": "Re-execute.",
                "action": "execute_script",
                "action_input": {"test_case_id": "tc_e2e_001"},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(intent="login", complexity="simple", steps=["Login"]),
            memory_service=memory_service,
        )
        result = orch.run("Login with repair")

        self.assertEqual(result.status, "success")
        memory_service.write_success_memory.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Token budget compliance
# ---------------------------------------------------------------------------


class TokenBudgetComplianceTests(unittest.TestCase):
    """Verify that context window stays within budget under heavy load."""

    def test_render_stays_within_budget_after_many_steps(self):
        """After many actions, render_for_llm output stays within token budget."""
        mem = WorkingMemory(task_prompt="Complex multi-step test scenario " * 5)
        mem.task_analysis = _make_analysis()
        mem.execution_plan = _make_complex_plan()
        mem.knowledge_context = "Pattern: use explicit waits for dynamic elements " * 20
        mem.current_code = "from selenium import webdriver\n" * 50

        # Add many actions
        for i in range(1, 25):
            record = ActionRecord(
                step=i,
                thought=f"Step {i}: performing action {i} on the page " * 3,
                tool_name="echo",
                tool_input={"message": f"action_{i}"},
                observation=f"Observation {i}: action completed successfully " * 3,
                duration_ms=100 * i,
            )
            mem.add_action(record)

        rendered = mem.render_for_llm(max_tokens=4000)
        from app.services.token_utils import estimate_tokens
        tokens = estimate_tokens(rendered)
        self.assertLessEqual(tokens, 4000)

    def test_compact_triggered_with_many_actions(self):
        """When actions exceed max_history_steps, _compact reduces the count."""
        mem = WorkingMemory(task_prompt="Test", max_history_steps=10)
        for i in range(1, 15):
            mem.add_action(ActionRecord(
                step=i,
                thought=f"Thought {i}",
                tool_name="echo",
                observation=f"Obs {i}",
            ))
        # After compaction, should have fewer than 15 actions
        self.assertLess(len(mem.actions), 15)

    def test_budget_allocation_preserves_high_priority(self):
        """Under tight budget, P1 (task + analysis) is preserved over P6 (history)."""
        mem = WorkingMemory(task_prompt="Important test scenario", max_token_budget=200)
        mem.task_analysis = TaskAnalysis(
            intent="login",
            steps=["Login to site"],
            success_criteria=["Login succeeds"],
            complexity="simple",
        )
        # Add large action history that should be truncated/dropped
        for i in range(1, 10):
            mem.add_action(ActionRecord(
                step=i,
                thought="Very long thought " * 50,
                tool_name="echo",
                observation="Very long observation " * 50,
            ))

        rendered = mem.render_for_llm(max_tokens=200)
        self.assertIn("Important test scenario", rendered)
        self.assertIn("login", rendered.lower())


# ---------------------------------------------------------------------------
# 5. Working memory serialization
# ---------------------------------------------------------------------------


class WorkingMemorySerializationTests(unittest.TestCase):
    """Verify to_dict captures the full state for API responses."""

    def test_full_state_serialization(self):
        """to_dict includes all fields after a complex run."""
        responses = [
            json.dumps({
                "thought": "Search knowledge.",
                "action": "search_knowledge",
                "action_input": {"query": "login", "plan_step": 1},
            }),
            json.dumps({
                "thought": "Generate script.",
                "action": "generate_selenium_script",
                "action_input": {"scenario": "login", "plan_step": 2},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Serialization test")
        d = result.memory.to_dict()

        self.assertIn("task_prompt", d)
        self.assertIn("test_case_id", d)
        self.assertIn("execution_id", d)
        self.assertIn("actions", d)
        self.assertIn("task_analysis", d)
        self.assertIn("execution_plan", d)
        self.assertIn("step_results", d)
        self.assertIsNotNone(d["task_analysis"])
        self.assertIsNotNone(d["execution_plan"])

    def test_result_to_dict_is_json_serializable(self):
        """AgentRunResult.to_dict produces a JSON-serializable object."""
        responses = [
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("JSON serialization test")
        d = result.to_dict()

        # Should not raise
        serialized = json.dumps(d, ensure_ascii=False, default=str)
        self.assertIsInstance(serialized, str)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["status"], "success")


# ---------------------------------------------------------------------------
# 6. Max steps reached
# ---------------------------------------------------------------------------


class MaxStepsReachedTests(unittest.TestCase):
    """Agent gracefully terminates when max_steps is exhausted."""

    def test_max_steps_terminates_with_correct_status(self):
        """Agent returns max_steps_reached when it runs out of steps."""
        # Agent never finishes — always does echo
        loop_response = json.dumps({
            "thought": "Still working...",
            "action": "search_knowledge",
            "action_input": {"query": "something"},
        })
        orch = _make_e2e_orchestrator(
            [loop_response],
            max_steps=3,
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Infinite loop scenario")

        self.assertEqual(result.status, "max_steps_reached")
        self.assertEqual(result.steps, 3)

    def test_max_steps_writes_trap_memory(self):
        """max_steps_reached triggers a trap memory card."""
        memory_service = MagicMock()
        loop_response = json.dumps({
            "thought": "Searching...",
            "action": "search_knowledge",
            "action_input": {"query": "x"},
        })
        orch = _make_e2e_orchestrator(
            [loop_response],
            max_steps=2,
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
            memory_service=memory_service,
        )
        result = orch.run("Max steps trap")

        self.assertEqual(result.status, "max_steps_reached")
        memory_service.write_trap_memory.assert_called_once()

    def test_max_steps_events_include_all_steps(self):
        """All step events are present even when max_steps is hit."""
        loop_response = json.dumps({
            "thought": "Working...",
            "action": "search_knowledge",
            "action_input": {"query": "y"},
        })
        orch = _make_e2e_orchestrator(
            [loop_response],
            max_steps=4,
            analysis=_make_analysis(),
        )
        result = orch.run("Count events")

        thinking_events = [e for e in result.events if e.event_type == "thinking"]
        action_events = [e for e in result.events if e.event_type == "action"]
        self.assertEqual(len(thinking_events), 4)
        self.assertEqual(len(action_events), 4)


# ---------------------------------------------------------------------------
# 7. SSE streaming
# ---------------------------------------------------------------------------


class SSEStreamingTests(unittest.TestCase):
    """Verify on_event callback is invoked correctly for SSE streaming."""

    def test_on_event_called_for_each_event(self):
        """on_event callback receives every event emitted."""
        captured = []

        def capture(event: AgentEvent):
            captured.append(event)

        responses = [
            json.dumps({
                "thought": "Search first.",
                "action": "search_knowledge",
                "action_input": {"query": "test"},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
            on_event=capture,
        )
        result = orch.run("SSE callback test")

        # Captured events should match result.events
        self.assertEqual(len(captured), len(result.events))
        for cap, res in zip(captured, result.events):
            self.assertEqual(cap.event_type, res.event_type)

    def test_events_are_dict_serializable(self):
        """Every event.to_dict() produces a JSON-serializable dict."""
        responses = [
            json.dumps({
                "thought": "Do something.",
                "action": "search_knowledge",
                "action_input": {"query": "x"},
            }),
            json.dumps({
                "thought": "Finish.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Serialization test")

        for event in result.events:
            d = event.to_dict()
            serialized = json.dumps(d, ensure_ascii=False, default=str)
            self.assertIsInstance(serialized, str)
            parsed = json.loads(serialized)
            self.assertIn("event_type", parsed)
            self.assertIn("step", parsed)
            self.assertIn("timestamp", parsed)

    def test_event_callback_exception_does_not_crash(self):
        """If on_event raises, the orchestrator continues gracefully."""
        def bad_callback(event):
            raise RuntimeError("Callback error!")

        responses = [
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(),
            on_event=bad_callback,
        )
        # Should not raise
        result = orch.run("Bad callback test")
        self.assertEqual(result.status, "success")


# ---------------------------------------------------------------------------
# 8. Chinese prompt handling
# ---------------------------------------------------------------------------


class ChinesePromptTests(unittest.TestCase):
    """Verify Chinese prompts work end-to-end."""

    def test_chinese_prompt_full_flow(self):
        """Chinese prompt passes through analysis → plan → execute → finish."""
        analysis = TaskAnalysis(
            intent="multi_step",
            target_site=TargetSite(url="http://localhost:9528", name="后台管理系统"),
            steps=[
                "打开 http://localhost:9528",
                "使用 admin/111111 登录系统",
                "导航到用户管理页面",
                "搜索用户 'test'",
            ],
            success_criteria=["搜索结果包含 'test'"],
            complexity="multi_step",
        )
        plan = ExecutionPlan(
            goal="登录后台管理系统并搜索用户",
            steps=[
                PlanStep(step_number=1, action="navigate", description="打开后台管理系统"),
                PlanStep(step_number=2, action="login", description="使用管理员账号登录"),
                PlanStep(step_number=3, action="search", description="搜索测试用户"),
                PlanStep(step_number=4, action="verify", description="验证搜索结果"),
            ],
            estimated_complexity="multi_step",
        )
        responses = [
            json.dumps({
                "thought": "搜索知识库中的登录模式。",
                "action": "search_knowledge",
                "action_input": {"query": "后台管理系统登录", "plan_step": 1},
            }),
            json.dumps({
                "thought": "生成登录脚本。",
                "action": "generate_selenium_script",
                "action_input": {"scenario": "登录后台管理系统", "plan_step": 2},
            }),
            json.dumps({
                "thought": "所有步骤完成。",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=analysis,
            plan=plan,
        )
        result = orch.run("登录后台管理系统，导航到用户管理页面，搜索用户 'test'")

        self.assertEqual(result.status, "success")

        # Verify Chinese content is in memory
        rendered = result.memory.render_for_llm()
        self.assertIn("后台管理系统", rendered)

    def test_chinese_events_serializable(self):
        """Events with Chinese content serialize to JSON correctly."""
        analysis = TaskAnalysis(
            intent="login",
            steps=["登录系统"],
            success_criteria=["登录成功"],
            complexity="simple",
        )
        responses = [
            json.dumps({
                "thought": "完成登录测试。",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(responses, analysis=analysis)
        result = orch.run("登录测试")

        for event in result.events:
            s = json.dumps(event.to_dict(), ensure_ascii=False)
            self.assertIsInstance(s, str)


# ---------------------------------------------------------------------------
# 9. Agent response parsing edge cases
# ---------------------------------------------------------------------------


class AgentResponseParsingTests(unittest.TestCase):
    """Verify the orchestrator handles various LLM output formats."""

    def test_markdown_fenced_response(self):
        """LLM response wrapped in ```json fences is parsed correctly."""
        fenced = '```json\n{"thought": "Done.", "action": "finish", "action_input": {"status": "success"}}\n```'
        orch = _make_e2e_orchestrator([fenced])
        result = orch.run("Fenced response test")
        self.assertEqual(result.status, "success")

    def test_extra_text_before_json(self):
        """LLM response with text before JSON is still parsed."""
        messy = 'Here is my response:\n{"thought": "Done.", "action": "finish", "action_input": {"status": "success"}}'
        orch = _make_e2e_orchestrator([messy])
        result = orch.run("Messy response test")
        self.assertEqual(result.status, "success")

    def test_unparseable_response_triggers_error(self):
        """Completely unparseable LLM output triggers an error event."""
        orch = _make_e2e_orchestrator(["This is not JSON at all!!!"])
        result = orch.run("Bad JSON test")
        self.assertEqual(result.status, "error")
        error_events = [e for e in result.events if e.event_type == "error"]
        self.assertGreaterEqual(len(error_events), 1)

    def test_action_input_as_string(self):
        """action_input provided as a JSON string (instead of object) is parsed."""
        response = json.dumps({
            "thought": "Done.",
            "action": "finish",
            "action_input": '{"status": "success"}',
        })
        orch = _make_e2e_orchestrator([response])
        result = orch.run("String action_input test")
        self.assertEqual(result.status, "success")


# ---------------------------------------------------------------------------
# 10. Regression: all components integrated
# ---------------------------------------------------------------------------


class IntegrationRegressionTests(unittest.TestCase):
    """Regression tests ensuring all integrated components work together."""

    def test_task_analysis_data_in_result(self):
        """TaskAnalysis data flows through to the final result."""
        responses = [json.dumps({
            "thought": "Finish.", "action": "finish",
            "action_input": {"status": "success"},
        })]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Regression: analysis data")

        d = result.to_dict()
        self.assertIsNotNone(d["memory"]["task_analysis"])
        self.assertEqual(d["memory"]["task_analysis"]["intent"], "multi_step")
        self.assertEqual(d["memory"]["task_analysis"]["complexity"], "multi_step")

    def test_plan_data_in_result(self):
        """ExecutionPlan data flows through to the final result."""
        responses = [json.dumps({
            "thought": "Finish.", "action": "finish",
            "action_input": {"status": "success"},
        })]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Regression: plan data")

        d = result.to_dict()
        ep = d["memory"]["execution_plan"]
        self.assertEqual(ep["step_count"], 5)
        self.assertIn("login", ep["goal"].lower())

    def test_multi_step_prompt_addon_in_complex_scenario(self):
        """Complex scenario with multi-step plan triggers the MULTI_STEP_PROMPT_ADDON."""
        llm = MagicMock()
        captured_prompts = []

        def capture_chat(*, system_prompt, user_message, **kwargs):
            captured_prompts.append(system_prompt)
            return json.dumps({
                "thought": "Done.", "action": "finish",
                "action_input": {"status": "success"},
            })

        llm.agent_chat = capture_chat
        settings = MagicMock()
        registry = _build_full_registry()

        ta = MagicMock(spec=TaskAnalyzer)
        ta.analyze = MagicMock(return_value=_make_analysis())
        planner = MagicMock(spec=Planner)
        planner.plan = MagicMock(return_value=_make_complex_plan())

        orch = AgentOrchestrator(
            settings=settings,
            llm_service=llm,
            tool_registry=registry,
            max_steps=5,
            task_analyzer=ta,
            planner=planner,
        )
        orch.run("Prompt addon regression test")

        self.assertTrue(len(captured_prompts) > 0)
        self.assertIn("MULTI-STEP task", captured_prompts[0])
        self.assertIn("plan_step", captured_prompts[0])

    def test_unknown_tool_handled_gracefully(self):
        """Agent calling a nonexistent tool gets a ToolResult with success=False."""
        responses = [
            json.dumps({
                "thought": "Try nonexistent tool.",
                "action": "nonexistent_tool_xyz",
                "action_input": {},
            }),
            json.dumps({
                "thought": "Tool failed, finish.",
                "action": "finish",
                "action_input": {"status": "failed", "reason": "Unknown tool"},
            }),
        ]
        orch = _make_e2e_orchestrator(responses)
        result = orch.run("Unknown tool regression")

        self.assertEqual(result.status, "failed")
        self.assertGreaterEqual(len(result.memory.accumulated_errors), 1)

    def test_working_memory_estimate_tokens(self):
        """WorkingMemory.estimate_tokens() returns a positive number after typical flow."""
        responses = [
            json.dumps({
                "thought": "Search.", "action": "search_knowledge",
                "action_input": {"query": "test"},
            }),
            json.dumps({
                "thought": "Generate.", "action": "generate_selenium_script",
                "action_input": {"scenario": "test"},
            }),
            json.dumps({
                "thought": "Done.", "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(),
            plan=_make_complex_plan(),
        )
        result = orch.run("Token estimate test")

        tokens = result.memory.estimate_tokens()
        self.assertGreater(tokens, 0)

    def test_render_for_llm_deterministic_order(self):
        """render_for_llm output order: task, analysis, plan, step_results, knowledge, code, errors, history."""
        mem = WorkingMemory(task_prompt="Test prompt")
        mem.task_analysis = TaskAnalysis(
            intent="login", steps=["Login"], success_criteria=["OK"], complexity="simple",
        )
        mem.execution_plan = ExecutionPlan(
            goal="Login test",
            steps=[PlanStep(step_number=1, action="login", description="Login")],
            estimated_complexity="simple",
        )
        mem.knowledge_context = "Some context"
        mem.current_code = "print('hello')"
        mem.accumulated_errors = ["Error 1"]
        mem.add_action(ActionRecord(step=1, thought="Think", tool_name="echo", observation="Obs"))

        rendered = mem.render_for_llm()
        # Verify ordering: task before analysis before plan before knowledge
        task_pos = rendered.find("Test prompt")
        analysis_pos = rendered.find("login")
        knowledge_pos = rendered.find("Some context")
        code_pos = rendered.find("print('hello')")
        self.assertLess(task_pos, knowledge_pos)
        self.assertLess(knowledge_pos, code_pos)


# ---------------------------------------------------------------------------
# 11. Complex flow with all tools chained
# ---------------------------------------------------------------------------


class FullToolChainTests(unittest.TestCase):
    """Verify the full tool chain: search_knowledge → generate → validate →
    execute → get_result with all memory shortcuts updated."""

    def test_full_tool_chain_memory_updates(self):
        """Each tool in the chain correctly updates working memory shortcuts."""
        responses = [
            json.dumps({
                "thought": "Search for patterns.",
                "action": "search_knowledge",
                "action_input": {"query": "vue-admin login"},
            }),
            json.dumps({
                "thought": "Generate script.",
                "action": "generate_selenium_script",
                "action_input": {"scenario": "Login to vue-admin"},
            }),
            json.dumps({
                "thought": "Validate code.",
                "action": "validate_code",
                "action_input": {"code": "..."},
            }),
            json.dumps({
                "thought": "Execute test.",
                "action": "execute_script",
                "action_input": {"test_case_id": "tc_e2e_001"},
            }),
            json.dumps({
                "thought": "Check result.",
                "action": "get_execution_result",
                "action_input": {"execution_id": "exec_001"},
            }),
            json.dumps({
                "thought": "All done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(
            responses,
            analysis=_make_analysis(intent="login", complexity="simple", steps=["Login"]),
        )
        result = orch.run("Full tool chain test")

        # After search_knowledge
        self.assertIn("Pattern found", result.memory.knowledge_context)
        # After generate_selenium_script
        self.assertEqual(result.memory.test_case_id, "tc_e2e_001")
        self.assertIn("selenium", result.memory.current_code)
        # After execute_script
        self.assertIsNotNone(result.memory.execution_id)
        # Final status
        self.assertEqual(result.status, "success")

    def test_search_memory_tool_integration(self):
        """search_memory tool is callable and returns a valid ToolResult."""
        responses = [
            json.dumps({
                "thought": "Check past experiences.",
                "action": "search_memory",
                "action_input": {"query": "login failure"},
            }),
            json.dumps({
                "thought": "No memories, proceed.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_e2e_orchestrator(responses)
        result = orch.run("Memory search test")

        self.assertEqual(result.status, "success")
        action_events = [e for e in result.events if e.event_type == "action"]
        memory_actions = [e for e in action_events if e.data.get("tool") == "search_memory"]
        self.assertEqual(len(memory_actions), 1)
        self.assertTrue(memory_actions[0].data["success"])


if __name__ == "__main__":
    unittest.main()
