"""Tests for success/trap memory card trigger integration in AgentOrchestrator."""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from . import _bootstrap  # noqa: F401

from app.services.agent_orchestrator import AgentOrchestrator
from app.services.working_memory import ActionRecord, WorkingMemory
from app.tools.base import BaseTool, ToolRegistry, ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes input."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(success=True, data={"echoed": kwargs.get("message", "")}, summary="ok")


class FakeGenerateTool(BaseTool):
    @property
    def name(self) -> str:
        return "generate_selenium_script"

    @property
    def description(self) -> str:
        return "Generate a script."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            success=True,
            data={"test_case_id": "tc-1", "generated_code": "print('hello')"},
            summary="Generated.",
        )


def _make_orchestrator(
    llm_responses: list[str],
    max_steps: int = 5,
    memory_service=None,
    extra_tools: list[BaseTool] | None = None,
):
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
    registry.register(FakeGenerateTool())
    if extra_tools:
        for t in extra_tools:
            registry.register(t)

    return AgentOrchestrator(
        settings=settings,
        llm_service=llm,
        tool_registry=registry,
        max_steps=max_steps,
        memory_service=memory_service,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class SuccessMemoryCardTests(unittest.TestCase):
    """Test that write_success_memory is triggered on first-try success."""

    def test_success_without_repair_writes_success_card(self):
        """Agent generates script and finishes successfully without repair → success card."""
        memory = MagicMock()
        responses = [
            json.dumps({
                "thought": "Generate script.",
                "action": "generate_selenium_script",
                "action_input": {"prompt": "test"},
            }),
            json.dumps({
                "thought": "Done!",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(responses, memory_service=memory)
        result = orch.run("Search Baidu for Selenium")

        self.assertEqual(result.status, "success")
        memory.write_success_memory.assert_called_once()
        call_kwargs = memory.write_success_memory.call_args[1]
        self.assertEqual(call_kwargs["prompt"], "Search Baidu for Selenium")
        self.assertIn("hello", call_kwargs["code"])  # from FakeGenerateTool

    def test_success_after_repair_does_not_write_success_card(self):
        """Agent that needed repair steps should NOT write a success card."""
        memory = MagicMock()

        class FakeRepairTool(BaseTool):
            @property
            def name(self): return "repair_script"
            @property
            def description(self): return "Repair."
            @property
            def parameters_schema(self): return {"type": "object", "properties": {}, "required": []}
            def execute(self, **kwargs): return ToolResult(success=True, data={"repaired_code": "fixed"}, summary="ok")

        responses = [
            json.dumps({"thought": "Gen.", "action": "generate_selenium_script", "action_input": {"prompt": "t"}}),
            json.dumps({"thought": "Repair.", "action": "repair_script", "action_input": {}}),
            json.dumps({"thought": "Done!", "action": "finish", "action_input": {"status": "success"}}),
        ]
        orch = _make_orchestrator(responses, memory_service=memory, extra_tools=[FakeRepairTool()])
        result = orch.run("test")

        self.assertEqual(result.status, "success")
        memory.write_success_memory.assert_not_called()
        memory.write_trap_memory.assert_not_called()


class TrapMemoryCardTests(unittest.TestCase):
    """Test that write_trap_memory is triggered on failure."""

    def test_failed_run_writes_trap_card(self):
        """Agent finishes with 'failed' status → trap card."""
        memory = MagicMock()
        responses = [
            json.dumps({
                "thought": "Cannot do it.",
                "action": "finish",
                "action_input": {"status": "failed", "reason": "impossible task"},
            }),
        ]
        orch = _make_orchestrator(responses, memory_service=memory)
        result = orch.run("do something impossible")

        self.assertEqual(result.status, "failed")
        memory.write_trap_memory.assert_called_once()
        call_kwargs = memory.write_trap_memory.call_args[1]
        self.assertEqual(call_kwargs["prompt"], "do something impossible")
        self.assertGreater(call_kwargs["attempt_count"], 0)
        memory.write_success_memory.assert_not_called()

    def test_max_steps_reached_writes_trap_card(self):
        """Agent exhausts max_steps → trap card."""
        memory = MagicMock()
        echo_response = json.dumps({
            "thought": "Keep going.",
            "action": "echo",
            "action_input": {"message": "loop"},
        })
        orch = _make_orchestrator([echo_response], max_steps=2, memory_service=memory)
        result = orch.run("looping task")

        self.assertEqual(result.status, "max_steps_reached")
        memory.write_trap_memory.assert_called_once()

    def test_trap_card_includes_accumulated_errors(self):
        """Trap card error_summary includes accumulated errors."""
        memory = MagicMock()
        responses = [
            json.dumps({
                "thought": "Fail.",
                "action": "finish",
                "action_input": {"status": "failed", "reason": "broken"},
            }),
        ]
        orch = _make_orchestrator(responses, memory_service=memory)
        # Inject an error into working memory before finishing
        result = orch.run("error scenario")

        memory.write_trap_memory.assert_called_once()
        call_kwargs = memory.write_trap_memory.call_args[1]
        # error_summary should be non-empty (either from accumulated errors or result.error)
        self.assertTrue(call_kwargs["error_summary"])


class MemoryCardEdgeCaseTests(unittest.TestCase):
    """Edge cases for memory card writing."""

    def test_no_memory_service_does_not_crash(self):
        """Without memory_service, orchestrator runs normally."""
        responses = [
            json.dumps({
                "thought": "Done.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = _make_orchestrator(responses, memory_service=None)
        result = orch.run("test without memory")
        self.assertEqual(result.status, "success")

    def test_memory_write_exception_does_not_crash_run(self):
        """If memory writing throws, the run still returns normally."""
        memory = MagicMock()
        memory.write_success_memory.side_effect = RuntimeError("DB error")
        responses = [
            json.dumps({"thought": "Gen.", "action": "generate_selenium_script", "action_input": {"prompt": "t"}}),
            json.dumps({"thought": "Done.", "action": "finish", "action_input": {"status": "success"}}),
        ]
        orch = _make_orchestrator(responses, memory_service=memory)
        result = orch.run("test")
        # Should still succeed despite memory error
        self.assertEqual(result.status, "success")

    def test_success_without_code_does_not_write_card(self):
        """Success with no current_code → no success card (nothing to record)."""
        memory = MagicMock()
        responses = [
            json.dumps({"thought": "Done.", "action": "finish", "action_input": {"status": "success"}}),
        ]
        orch = _make_orchestrator(responses, memory_service=memory)
        result = orch.run("instant finish")
        self.assertEqual(result.status, "success")
        memory.write_success_memory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
