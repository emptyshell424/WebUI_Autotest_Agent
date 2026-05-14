"""Tests for the agent core: ToolRegistry, WorkingMemory, AgentOrchestrator."""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock

from app.services.agent_orchestrator import AgentOrchestrator
from app.services.working_memory import ActionRecord, WorkingMemory
from app.tools.base import BaseTool, ToolRegistry, ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class EchoTool(BaseTool):
    """A trivial tool for testing: echoes back its input."""

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
            "properties": {
                "message": {"type": "string"},
            },
            "required": ["message"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            success=True,
            data={"echoed": kwargs.get("message", "")},
            summary=f"Echoed: {kwargs.get('message', '')}",
        )


class FailTool(BaseTool):
    """Always fails."""

    @property
    def name(self) -> str:
        return "fail_tool"

    @property
    def description(self) -> str:
        return "Always fails."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("intentional failure")


# ---------------------------------------------------------------------------
# ToolRegistry tests
# ---------------------------------------------------------------------------


class ToolRegistryTests(unittest.TestCase):
    def test_register_and_list(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        self.assertIn("echo", registry.list_names())
        self.assertEqual(len(registry.list_tools()), 1)

    def test_invoke_registered_tool(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        result = registry.invoke("echo", {"message": "hello"})
        self.assertTrue(result.success)
        self.assertEqual(result.data["echoed"], "hello")

    def test_invoke_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.invoke("nonexistent", {})
        self.assertFalse(result.success)
        self.assertIn("Unknown tool", result.error)

    def test_invoke_catches_exception(self):
        registry = ToolRegistry()
        registry.register(FailTool())
        result = registry.invoke("fail_tool", {})
        self.assertFalse(result.success)
        self.assertIn("intentional failure", result.error)

    def test_to_function_schemas(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        schemas = registry.to_function_schemas()
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["type"], "function")
        self.assertEqual(schemas[0]["function"]["name"], "echo")


# ---------------------------------------------------------------------------
# WorkingMemory tests
# ---------------------------------------------------------------------------


class WorkingMemoryTests(unittest.TestCase):
    def test_add_action_and_render(self):
        mem = WorkingMemory(task_prompt="Test searching Baidu")
        mem.add_action(ActionRecord(step=1, thought="Search knowledge first", tool_name="search_knowledge"))
        rendered = mem.render_for_llm()
        self.assertIn("Test searching Baidu", rendered)
        self.assertIn("search_knowledge", rendered)

    def test_compact_when_exceeding_max(self):
        mem = WorkingMemory(task_prompt="test", max_history_steps=4)
        for i in range(6):
            mem.add_action(ActionRecord(step=i + 1, thought=f"Step {i + 1}", tool_name="echo"))
        # Should have compacted — fewer actions than 6
        self.assertLess(len(mem.actions), 6)

    def test_record_error(self):
        mem = WorkingMemory(task_prompt="test")
        mem.record_error("timeout occurred")
        self.assertEqual(len(mem.accumulated_errors), 1)
        self.assertIn("timeout", mem.accumulated_errors[0])

    def test_to_dict(self):
        mem = WorkingMemory(task_prompt="test prompt")
        mem.test_case_id = "tc-123"
        d = mem.to_dict()
        self.assertEqual(d["task_prompt"], "test prompt")
        self.assertEqual(d["test_case_id"], "tc-123")


# ---------------------------------------------------------------------------
# AgentOrchestrator tests
# ---------------------------------------------------------------------------


class AgentOrchestratorTests(unittest.TestCase):
    def _make_orchestrator(self, llm_responses: list[str], max_steps: int = 5):
        """Create an orchestrator with a mock LLM that returns pre-defined responses."""
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

        return AgentOrchestrator(
            settings=settings,
            llm_service=llm,
            tool_registry=registry,
            max_steps=max_steps,
        )

    def test_simple_finish(self):
        """Agent responds with finish on the first step."""
        response = json.dumps({
            "thought": "Task is trivial, finishing.",
            "action": "finish",
            "action_input": {"status": "success"},
        })
        orch = self._make_orchestrator([response])
        result = orch.run("Say hello")
        self.assertEqual(result.status, "success")
        self.assertGreaterEqual(result.steps, 1)

    def test_tool_call_then_finish(self):
        """Agent calls echo tool, then finishes."""
        responses = [
            json.dumps({
                "thought": "Let me echo a message.",
                "action": "echo",
                "action_input": {"message": "hello world"},
            }),
            json.dumps({
                "thought": "Echo worked, finishing.",
                "action": "finish",
                "action_input": {"status": "success"},
            }),
        ]
        orch = self._make_orchestrator(responses)
        result = orch.run("Echo test")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.steps, 2)
        # Check events
        action_events = [e for e in result.events if e.event_type == "action"]
        self.assertEqual(len(action_events), 1)
        self.assertEqual(action_events[0].data["tool"], "echo")

    def test_max_steps_reached(self):
        """Agent never finishes — should stop at max_steps."""
        echo_response = json.dumps({
            "thought": "Keep echoing.",
            "action": "echo",
            "action_input": {"message": "loop"},
        })
        orch = self._make_orchestrator([echo_response], max_steps=3)
        result = orch.run("Loop test")
        self.assertEqual(result.status, "max_steps_reached")

    def test_events_are_emitted(self):
        """on_event callback is invoked for each step."""
        emitted = []

        response = json.dumps({
            "thought": "Finishing immediately.",
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
            on_event=lambda e: emitted.append(e),
        )
        orch.run("Quick test")
        self.assertGreater(len(emitted), 0)

    def test_parse_json_with_markdown_fencing(self):
        """LLM wraps response in ```json fencing — parser should handle it."""
        fenced = '```json\n{"thought": "ok", "action": "finish", "action_input": {"status": "success"}}\n```'
        orch = self._make_orchestrator([fenced])
        result = orch.run("Fenced test")
        self.assertEqual(result.status, "success")


if __name__ == "__main__":
    unittest.main()
