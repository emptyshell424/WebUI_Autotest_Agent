"""Tests for multi-step script composition execution.

Validates:
1. Planner integration into AgentOrchestrator
2. Plan event emission
3. Multi-step system prompt enhancement
4. Plan step tracking via action_input['plan_step']
5. Step results accumulated in WorkingMemory
6. Render for LLM includes plan + step results
7. WorkingMemory serialization with plan data
8. Graceful fallback when planner fails
9. Single-step plan (no MULTI_STEP_PROMPT_ADDON)
10. Edge cases (missing plan_step key, invalid plan_step type)
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock

from app.services.agent_orchestrator import (
    MULTI_STEP_PROMPT_ADDON,
    AgentOrchestrator,
)
from app.services.planner import ExecutionPlan, PlanStep, Planner
from app.services.task_analyzer import TaskAnalysis, TargetSite
from app.services.working_memory import WorkingMemory
from app.tools.base import BaseTool, ToolRegistry, ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class EchoTool(BaseTool):
    """Trivial tool for testing."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes the input message."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            success=True,
            data={"echoed": kwargs.get("message", "")},
            summary=f"Echoed: {kwargs.get('message', '')}",
        )


def _make_task_analysis(
    intent: str = "multi_step",
    complexity: str = "multi_step",
    steps: list[str] | None = None,
) -> TaskAnalysis:
    return TaskAnalysis(
        intent=intent,
        target_site=TargetSite(url="http://localhost:9528", name="vue-admin"),
        steps=steps or [
            "Navigate to http://localhost:9528",
            "Login with admin/111111",
            "Navigate to user management page",
            "Search for user 'test'",
        ],
        success_criteria=["Search results contain 'test'"],
        complexity=complexity,
    )


def _make_multi_step_plan() -> ExecutionPlan:
    return ExecutionPlan(
        goal="Login and search for user 'test'",
        steps=[
            PlanStep(step_number=1, action="navigate", description="Open http://localhost:9528"),
            PlanStep(step_number=2, action="login", description="Login with admin/111111", depends_on=[1]),
            PlanStep(step_number=3, action="navigate", description="Go to user management", depends_on=[2]),
            PlanStep(step_number=4, action="search", description="Search for user 'test'", depends_on=[3]),
            PlanStep(step_number=5, action="verify", description="Verify search results", depends_on=[4]),
        ],
        estimated_complexity="multi_step",
    )


def _make_single_step_plan() -> ExecutionPlan:
    return ExecutionPlan(
        goal="Open Baidu",
        steps=[
            PlanStep(step_number=1, action="navigate", description="Open https://www.baidu.com"),
        ],
        estimated_complexity="simple",
    )


def _make_orchestrator(
    llm_responses: list[str],
    max_steps: int = 10,
    *,
    task_analysis: TaskAnalysis | None = None,
    plan: ExecutionPlan | None = None,
    planner_raises: bool = False,
) -> AgentOrchestrator:
    settings = MagicMock()
    llm = MagicMock()
    call_count = {"n": 0}

    def fake_agent_chat(*, system_prompt, user_message):
        idx = min(call_count["n"], len(llm_responses) - 1)
        call_count["n"] += 1
        return llm_responses[idx]

    llm.agent_chat = fake_agent_chat

    registry = ToolRegistry()
    registry.register(EchoTool())

    # Mock TaskAnalyzer
    task_analyzer = None
    if task_analysis is not None:
        task_analyzer = MagicMock()
        task_analyzer.analyze = MagicMock(return_value=task_analysis)

    # Mock Planner
    planner = None
    if plan is not None or planner_raises:
        planner = MagicMock(spec=Planner)
        if planner_raises:
            planner.plan = MagicMock(side_effect=RuntimeError("LLM unavailable"))
        else:
            planner.plan = MagicMock(return_value=plan)

    return AgentOrchestrator(
        settings=settings,
        llm_service=llm,
        tool_registry=registry,
        max_steps=max_steps,
        task_analyzer=task_analyzer,
        planner=planner,
    )


# ---------------------------------------------------------------------------
# Tests: Planner integration into AgentOrchestrator
# ---------------------------------------------------------------------------


class PlannerIntegrationTests(unittest.TestCase):
    """Verify that the orchestrator calls the Planner and emits plan events."""

    def test_plan_event_emitted_for_multi_step_task(self):
        """When task_analyzer + planner are set, a 'plan' event is emitted at step 0."""
        response = json.dumps({
            "thought": "Plan received, finishing.",
            "action": "finish",
            "action_input": {"status": "success"},
        })
        orch = _make_orchestrator(
            [response],
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Login and search for user test")

        plan_events = [e for e in result.events if e.event_type == "plan"]
        self.assertEqual(len(plan_events), 1)
        self.assertEqual(plan_events[0].step, 0)
        self.assertEqual(plan_events[0].data["step_count"], 5)
        self.assertEqual(plan_events[0].data["goal"], "Login and search for user 'test'")

    def test_plan_stored_in_memory(self):
        """The execution plan is stored in working memory."""
        response = json.dumps({
            "thought": "Done.",
            "action": "finish",
            "action_input": {"status": "success"},
        })
        plan = _make_multi_step_plan()
        orch = _make_orchestrator(
            [response],
            task_analysis=_make_task_analysis(),
            plan=plan,
        )
        result = orch.run("Login and search")

        self.assertIsNotNone(result.memory.execution_plan)
        self.assertEqual(result.memory.execution_plan.step_count, 5)

    def test_task_analysis_event_before_plan(self):
        """task_analysis event should appear before plan event."""
        response = json.dumps({
            "thought": "Done.",
            "action": "finish",
            "action_input": {"status": "success"},
        })
        orch = _make_orchestrator(
            [response],
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Test ordering")

        event_types = [e.event_type for e in result.events]
        ta_idx = event_types.index("task_analysis")
        plan_idx = event_types.index("plan")
        self.assertLess(ta_idx, plan_idx)

    def test_no_plan_without_task_analysis(self):
        """If task analyzer is not set, planner should not be called."""
        response = json.dumps({
            "thought": "Done.",
            "action": "finish",
            "action_input": {"status": "success"},
        })
        planner = MagicMock(spec=Planner)
        settings = MagicMock()
        llm = MagicMock()
        llm.agent_chat = lambda *, system_prompt, user_message: response

        orch = AgentOrchestrator(
            settings=settings,
            llm_service=llm,
            tool_registry=ToolRegistry(),
            max_steps=5,
            planner=planner,
        )
        result = orch.run("Simple test")

        planner.plan.assert_not_called()
        plan_events = [e for e in result.events if e.event_type == "plan"]
        self.assertEqual(len(plan_events), 0)

    def test_planner_failure_graceful(self):
        """If planner raises, orchestrator continues without a plan."""
        response = json.dumps({
            "thought": "No plan, but finishing.",
            "action": "finish",
            "action_input": {"status": "success"},
        })
        orch = _make_orchestrator(
            [response],
            task_analysis=_make_task_analysis(),
            planner_raises=True,
        )
        result = orch.run("Test with broken planner")

        self.assertEqual(result.status, "success")
        self.assertIsNone(result.memory.execution_plan)


# ---------------------------------------------------------------------------
# Tests: Multi-step system prompt
# ---------------------------------------------------------------------------


class MultiStepPromptTests(unittest.TestCase):
    """Verify that multi-step plans enhance the system prompt."""

    def test_multi_step_prompt_addon_included(self):
        """Multi-step plan triggers MULTI_STEP_PROMPT_ADDON in system prompt."""
        llm = MagicMock()
        captured_prompts = []

        def capture_chat(*, system_prompt, user_message):
            captured_prompts.append(system_prompt)
            return json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            })

        llm.agent_chat = capture_chat
        settings = MagicMock()
        registry = ToolRegistry()
        registry.register(EchoTool())

        ta = MagicMock()
        ta.analyze = MagicMock(return_value=_make_task_analysis())
        planner = MagicMock(spec=Planner)
        planner.plan = MagicMock(return_value=_make_multi_step_plan())

        orch = AgentOrchestrator(
            settings=settings,
            llm_service=llm,
            tool_registry=registry,
            max_steps=5,
            task_analyzer=ta,
            planner=planner,
        )
        orch.run("Multi-step test")

        self.assertTrue(len(captured_prompts) > 0)
        self.assertIn("MULTI-STEP task", captured_prompts[0])

    def test_single_step_no_addon(self):
        """Single-step plan does NOT trigger MULTI_STEP_PROMPT_ADDON."""
        llm = MagicMock()
        captured_prompts = []

        def capture_chat(*, system_prompt, user_message):
            captured_prompts.append(system_prompt)
            return json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            })

        llm.agent_chat = capture_chat
        settings = MagicMock()
        registry = ToolRegistry()
        registry.register(EchoTool())

        ta = MagicMock()
        ta.analyze = MagicMock(return_value=_make_task_analysis(
            complexity="simple", steps=["Open Baidu"],
        ))
        planner = MagicMock(spec=Planner)
        planner.plan = MagicMock(return_value=_make_single_step_plan())

        orch = AgentOrchestrator(
            settings=settings,
            llm_service=llm,
            tool_registry=registry,
            max_steps=5,
            task_analyzer=ta,
            planner=planner,
        )
        orch.run("Simple test")

        self.assertTrue(len(captured_prompts) > 0)
        self.assertNotIn("MULTI-STEP task", captured_prompts[0])


# ---------------------------------------------------------------------------
# Tests: Plan step tracking
# ---------------------------------------------------------------------------


class PlanStepTrackingTests(unittest.TestCase):
    """Verify that plan_step in action_input triggers step result tracking."""

    def test_plan_step_tracking_on_tool_call(self):
        """When agent includes plan_step in action_input, step result is recorded."""
        responses = [
            json.dumps({
                "thought": "Executing plan step 1.",
                "action": "echo",
                "action_input": {"message": "navigate", "plan_step": 1},
            }),
            json.dumps({
                "thought": "Step 1 done, finishing.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(
            responses,
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Multi-step test")

        self.assertEqual(len(result.memory.step_results), 1)
        sr = result.memory.step_results[0]
        self.assertEqual(sr["step_number"], 1)
        self.assertEqual(sr["status"], "completed")
        self.assertEqual(sr["action"], "navigate")
        self.assertEqual(sr["tool_used"], "echo")

    def test_plan_step_complete_event_emitted(self):
        """A 'plan_step_complete' event is emitted when plan_step is tracked."""
        responses = [
            json.dumps({
                "thought": "Step 2.",
                "action": "echo",
                "action_input": {"message": "login", "plan_step": 2},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(
            responses,
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Test events")

        psc_events = [e for e in result.events if e.event_type == "plan_step_complete"]
        self.assertEqual(len(psc_events), 1)
        self.assertEqual(psc_events[0].data["step_number"], 2)
        self.assertEqual(psc_events[0].data["action"], "login")

    def test_multiple_plan_steps_tracked(self):
        """Multiple plan steps tracked sequentially."""
        responses = [
            json.dumps({
                "thought": "Step 1.",
                "action": "echo",
                "action_input": {"message": "nav", "plan_step": 1},
            }),
            json.dumps({
                "thought": "Step 2.",
                "action": "echo",
                "action_input": {"message": "login", "plan_step": 2},
            }),
            json.dumps({
                "thought": "Step 3.",
                "action": "echo",
                "action_input": {"message": "go to users", "plan_step": 3},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(
            responses,
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Full flow test")

        self.assertEqual(len(result.memory.step_results), 3)
        self.assertEqual(result.memory.step_results[0]["step_number"], 1)
        self.assertEqual(result.memory.step_results[1]["step_number"], 2)
        self.assertEqual(result.memory.step_results[2]["step_number"], 3)

    def test_no_tracking_without_plan_step_key(self):
        """Without plan_step in action_input, no step result is recorded."""
        responses = [
            json.dumps({
                "thought": "Regular echo.",
                "action": "echo",
                "action_input": {"message": "hello"},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(
            responses,
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("No plan_step key")

        self.assertEqual(len(result.memory.step_results), 0)

    def test_no_tracking_for_single_step_plan(self):
        """Single-step plan does not trigger tracking even with plan_step."""
        responses = [
            json.dumps({
                "thought": "Step 1.",
                "action": "echo",
                "action_input": {"message": "nav", "plan_step": 1},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(
            responses,
            task_analysis=_make_task_analysis(complexity="simple", steps=["Open Baidu"]),
            plan=_make_single_step_plan(),
        )
        result = orch.run("Single step")

        self.assertEqual(len(result.memory.step_results), 0)

    def test_invalid_plan_step_type_ignored(self):
        """Non-numeric plan_step is silently ignored."""
        responses = [
            json.dumps({
                "thought": "Bad plan_step.",
                "action": "echo",
                "action_input": {"message": "x", "plan_step": "not_a_number"},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(
            responses,
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Bad plan_step type")

        self.assertEqual(len(result.memory.step_results), 0)

    def test_unknown_plan_step_number_uses_action_fallback(self):
        """Plan step number that doesn't exist in the plan still records with tool action."""
        responses = [
            json.dumps({
                "thought": "Step 99.",
                "action": "echo",
                "action_input": {"message": "x", "plan_step": 99},
            }),
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(
            responses,
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Unknown step number")

        self.assertEqual(len(result.memory.step_results), 1)
        sr = result.memory.step_results[0]
        self.assertEqual(sr["step_number"], 99)
        self.assertEqual(sr["action"], "echo")  # fallback to tool action
        self.assertEqual(sr["description"], "")  # no plan step found


# ---------------------------------------------------------------------------
# Tests: WorkingMemory rendering with plan
# ---------------------------------------------------------------------------


class WorkingMemoryPlanRenderTests(unittest.TestCase):
    """Verify that plan and step results are rendered in LLM context."""

    def test_render_includes_execution_plan(self):
        """render_for_llm includes the execution plan block."""
        mem = WorkingMemory(task_prompt="Test")
        mem.execution_plan = _make_multi_step_plan()
        rendered = mem.render_for_llm()

        self.assertIn("Execution plan", rendered)
        self.assertIn("Login and search for user 'test'", rendered)
        self.assertIn("[navigate]", rendered)
        self.assertIn("[login]", rendered)

    def test_render_includes_step_results(self):
        """render_for_llm includes plan step results."""
        mem = WorkingMemory(task_prompt="Test")
        mem.execution_plan = _make_multi_step_plan()
        mem.step_results = [
            {"step_number": 1, "status": "completed", "description": "Open site"},
            {"step_number": 2, "status": "failed", "description": "Login attempt"},
        ]
        rendered = mem.render_for_llm()

        self.assertIn("Plan step results", rendered)
        self.assertIn("Step 1: [completed]", rendered)
        self.assertIn("Step 2: [failed]", rendered)

    def test_render_without_plan_omits_section(self):
        """Without a plan, no plan sections appear."""
        mem = WorkingMemory(task_prompt="Test")
        rendered = mem.render_for_llm()

        self.assertNotIn("Execution plan", rendered)
        self.assertNotIn("Plan step results", rendered)

    def test_to_dict_includes_plan(self):
        """to_dict includes execution_plan and step_results."""
        mem = WorkingMemory(task_prompt="Test")
        mem.execution_plan = _make_multi_step_plan()
        mem.step_results = [
            {"step_number": 1, "status": "completed", "description": "Step 1"},
        ]
        d = mem.to_dict()

        self.assertIsNotNone(d["execution_plan"])
        self.assertEqual(d["execution_plan"]["step_count"], 5)
        self.assertEqual(len(d["step_results"]), 1)

    def test_to_dict_without_plan(self):
        """to_dict returns None for execution_plan when not set."""
        mem = WorkingMemory(task_prompt="Test")
        d = mem.to_dict()

        self.assertIsNone(d["execution_plan"])
        self.assertEqual(d["step_results"], [])


# ---------------------------------------------------------------------------
# Tests: Full multi-step orchestrator flow
# ---------------------------------------------------------------------------


class FullMultiStepFlowTests(unittest.TestCase):
    """End-to-end tests for the complete multi-step flow."""

    def test_full_multi_step_success(self):
        """Full flow: analysis → plan → execute steps → finish."""
        responses = [
            # Step 1: echo for navigate (plan step 1)
            json.dumps({
                "thought": "Navigate to site.",
                "action": "echo",
                "action_input": {"message": "navigating", "plan_step": 1},
            }),
            # Step 2: echo for login (plan step 2)
            json.dumps({
                "thought": "Login.",
                "action": "echo",
                "action_input": {"message": "logging in", "plan_step": 2},
            }),
            # Step 3: finish
            json.dumps({
                "thought": "All steps done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(
            responses,
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Full multi-step flow")

        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.memory.step_results), 2)

        # Verify event ordering
        event_types = [e.event_type for e in result.events]
        self.assertIn("task_analysis", event_types)
        self.assertIn("plan", event_types)
        self.assertIn("plan_step_complete", event_types)
        self.assertIn("finish", event_types)

    def test_multi_step_with_failed_step(self):
        """A failed tool call records the step as failed."""
        responses = [
            # Step 1: call unknown tool (will fail)
            json.dumps({
                "thought": "Try unknown tool.",
                "action": "nonexistent_tool",
                "action_input": {"plan_step": 1},
            }),
            # Step 2: finish after failure
            json.dumps({
                "thought": "Failed, finishing.",
                "action": "finish",
                "action_input": {"status": "failed", "reason": "Tool not found"},
            }),
        ]
        orch = _make_orchestrator(
            responses,
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Flow with failure")

        self.assertEqual(result.status, "failed")
        self.assertEqual(len(result.memory.step_results), 1)
        self.assertEqual(result.memory.step_results[0]["status"], "failed")

    def test_no_planner_still_works(self):
        """Without a planner, orchestrator works as before (no plan events)."""
        response = json.dumps({
            "thought": "Done.",
            "action": "finish",
            "action_input": {"status": "success"},
        })
        settings = MagicMock()
        llm = MagicMock()
        llm.agent_chat = lambda *, system_prompt, user_message: response

        orch = AgentOrchestrator(
            settings=settings,
            llm_service=llm,
            tool_registry=ToolRegistry(),
            max_steps=5,
        )
        result = orch.run("No planner test")

        self.assertEqual(result.status, "success")
        self.assertIsNone(result.memory.execution_plan)
        plan_events = [e for e in result.events if e.event_type == "plan"]
        self.assertEqual(len(plan_events), 0)

    def test_plan_in_result_to_dict(self):
        """AgentRunResult.to_dict includes plan data via memory."""
        response = json.dumps({
            "thought": "Done.",
            "action": "finish",
            "action_input": {"status": "success"},
        })
        orch = _make_orchestrator(
            [response],
            task_analysis=_make_task_analysis(),
            plan=_make_multi_step_plan(),
        )
        result = orch.run("Serialization test")

        d = result.to_dict()
        self.assertIn("execution_plan", d["memory"])
        self.assertIsNotNone(d["memory"]["execution_plan"])
        self.assertEqual(d["memory"]["execution_plan"]["step_count"], 5)


# ---------------------------------------------------------------------------
# Tests: MULTI_STEP_PROMPT_ADDON constant
# ---------------------------------------------------------------------------


class PromptAddonTests(unittest.TestCase):
    """Verify the MULTI_STEP_PROMPT_ADDON constant content."""

    def test_addon_mentions_plan_step_key(self):
        self.assertIn("plan_step", MULTI_STEP_PROMPT_ADDON)

    def test_addon_mentions_sequential_execution(self):
        self.assertIn("sequentially", MULTI_STEP_PROMPT_ADDON)

    def test_addon_mentions_finish(self):
        self.assertIn("finish", MULTI_STEP_PROMPT_ADDON)


if __name__ == "__main__":
    unittest.main()
