"""AgentOrchestrator: the core ReAct (Reasoning + Acting) loop.

This service replaces the linear generate → execute → retry pipeline with
an autonomous agent loop that can reason about what to do next and call
tools dynamically.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.llm_service import LLMService
from app.services.planner import ExecutionPlan, Planner
from app.services.task_analyzer import TaskAnalyzer
from app.services.working_memory import ActionRecord, WorkingMemory
from app.tools.base import ToolRegistry, ToolResult
from app.utils.code_parser import extract_json

logger = logging.getLogger("autotest.agent")

AGENT_SYSTEM_PROMPT = (
    "You are an autonomous Web-UI test automation agent. Your job is to:\n"
    "1. Understand the user's test scenario.\n"
    "2. Search the knowledge base for relevant patterns.\n"
    "3. Generate a Selenium script to implement the test.\n"
    "4. Execute the script and observe the result.\n"
    "5. If the execution fails, diagnose the failure and repair the script.\n"
    "6. Repeat until the test passes or you have exhausted your allowed steps.\n\n"
    "At each step, output a JSON object with exactly these keys:\n"
    '  "thought": a short reasoning string explaining your current analysis,\n'
    '  "action": the name of the tool to call (or "finish" to end),\n'
    '  "action_input": a JSON object of arguments for the tool.\n\n'
    "If action is \"finish\", set action_input to:\n"
    '  {{"status": "success"}} or {{"status": "failed", "reason": "..."}}.\n\n'
    "Available tools:\n{tool_descriptions}\n\n"
    "Rules:\n"
    "- Always search_knowledge before generating a script.\n"
    "- Always validate_code before executing.\n"
    "- If execution fails, use diagnose_failure then repair_script before retrying.\n"
    "- Never repeat the exact same action+input twice in a row.\n"
    "- Keep your thought concise (under 200 characters).\n"
)

MULTI_STEP_PROMPT_ADDON = (
    "\n\nThis is a MULTI-STEP task. An execution plan has been generated and is "
    "available in the working memory. Follow these additional rules:\n"
    "- Execute the plan steps sequentially. For each plan step, generate and "
    "execute a script that accomplishes that specific step.\n"
    "- When generating a script for step N, include context from the results of "
    "previous steps (e.g. the browser should already be on the correct page).\n"
    "- After each plan step's script executes successfully, proceed to the next "
    "plan step.\n"
    "- If a plan step fails, diagnose and repair before moving on.\n"
    "- Include a 'plan_step' key in your action_input to indicate which plan step "
    "number you are currently working on (integer).\n"
    "- When ALL plan steps are completed, finish with status 'success'.\n"
)


@dataclass(slots=True)
class AgentEvent:
    """A single observable event from the agent loop, for streaming to the UI."""

    event_type: str  # thinking | action | observation | error | finish
    step: int
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "step": self.step,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentRunResult:
    """Final result returned by the orchestrator after the agent loop completes."""

    run_id: str
    status: str  # success | failed | max_steps_reached | error
    steps: int
    memory: WorkingMemory
    events: list[AgentEvent] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "steps": self.steps,
            "test_case_id": self.memory.test_case_id,
            "execution_id": self.memory.execution_id,
            "error": self.error,
            "events": [e.to_dict() for e in self.events],
            "memory": self.memory.to_dict(),
        }


class AgentOrchestrator:
    """Drives the ReAct loop: Thought → Action → Observation → repeat."""

    def __init__(
        self,
        settings: Settings,
        llm_service: LLMService,
        tool_registry: ToolRegistry,
        max_steps: int = 15,
        on_event: Callable[[AgentEvent], None] | None = None,
        task_analyzer: TaskAnalyzer | None = None,
        memory_service=None,
        planner: Planner | None = None,
    ) -> None:
        self.settings = settings
        self.llm_service = llm_service
        self.tool_registry = tool_registry
        self.max_steps = max_steps
        self._on_event = on_event
        self._task_analyzer = task_analyzer
        self._memory = memory_service
        self._planner = planner

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, prompt: str) -> AgentRunResult:
        """Execute the full agent loop for the given user prompt."""
        run_id = str(uuid.uuid4())
        memory = WorkingMemory(task_prompt=prompt)
        events: list[AgentEvent] = []
        status = "max_steps_reached"
        error: str | None = None

        # --- Run task analysis before the ReAct loop ---
        if self._task_analyzer is not None:
            try:
                analysis = self._task_analyzer.analyze(prompt)
                memory.task_analysis = analysis
                events.append(AgentEvent(
                    event_type="task_analysis",
                    step=0,
                    data=analysis.to_dict(),
                ))
                self._emit(events[-1])
                logger.info(
                    "Task analysis: intent=%s complexity=%s steps=%d",
                    analysis.intent, analysis.complexity, len(analysis.steps),
                )
            except Exception:
                logger.warning("Task analysis failed, continuing without it", exc_info=True)

        # --- Generate execution plan for multi-step tasks ---
        if self._planner is not None and memory.task_analysis is not None:
            try:
                plan = self._planner.plan(memory.task_analysis)
                memory.execution_plan = plan
                events.append(AgentEvent(
                    event_type="plan",
                    step=0,
                    data=plan.to_dict(),
                ))
                self._emit(events[-1])
                logger.info(
                    "Execution plan: goal=%s steps=%d complexity=%s",
                    plan.goal, plan.step_count, plan.estimated_complexity,
                )
            except Exception:
                logger.warning("Plan generation failed, continuing without it", exc_info=True)

        system_prompt = self._build_system_prompt(memory)

        for step in range(1, self.max_steps + 1):
            try:
                thought, action, action_input = self._reason(
                    system_prompt=system_prompt,
                    memory=memory,
                    step=step,
                )
            except Exception as exc:
                logger.exception("Agent reasoning failed at step %d", step)
                error = f"Reasoning failed: {exc}"
                events.append(AgentEvent(event_type="error", step=step, data={"error": error}))
                self._emit(events[-1])
                status = "error"
                break

            # Emit thinking event
            events.append(AgentEvent(
                event_type="thinking",
                step=step,
                data={"thought": thought, "action": action},
            ))
            self._emit(events[-1])

            # Check for finish
            if action == "finish":
                finish_status = (action_input or {}).get("status", "success")
                finish_reason = (action_input or {}).get("reason")
                record = ActionRecord(step=step, thought=thought, tool_name="finish")
                record.observation = f"Agent finished: {finish_status}"
                memory.add_action(record)
                status = finish_status if finish_status in ("success", "failed") else "success"
                if finish_reason:
                    error = finish_reason
                events.append(AgentEvent(
                    event_type="finish",
                    step=step,
                    data={"status": status, "reason": finish_reason},
                ))
                self._emit(events[-1])
                break

            # Execute tool
            t0 = time.time()
            tool_result = self.tool_registry.invoke(action, action_input or {})
            duration_ms = int((time.time() - t0) * 1000)

            observation = tool_result.to_observation()
            record = ActionRecord(
                step=step,
                thought=thought,
                tool_name=action,
                tool_input=action_input,
                observation=observation,
                duration_ms=duration_ms,
            )
            memory.add_action(record)

            # Update memory shortcuts based on tool results
            self._update_memory_from_result(memory, action, tool_result)

            # Track plan step completion
            self._track_plan_step(memory, action, action_input, tool_result, events, step)

            # Emit action + observation events
            events.append(AgentEvent(
                event_type="action",
                step=step,
                data={
                    "tool": action,
                    "input_keys": list((action_input or {}).keys()),
                    "success": tool_result.success,
                    "observation": observation[:500],
                    "duration_ms": duration_ms,
                },
            ))
            self._emit(events[-1])

        result = AgentRunResult(
            run_id=run_id,
            status=status,
            steps=len(memory.actions),
            memory=memory,
            events=events,
            error=error,
        )
        logger.info(
            "Agent run %s finished: status=%s steps=%d",
            run_id, status, result.steps,
        )

        # Write memory cards based on outcome
        self._write_memory_cards(result)

        return result

    # ------------------------------------------------------------------
    # LLM reasoning step
    # ------------------------------------------------------------------

    def _reason(
        self,
        *,
        system_prompt: str,
        memory: WorkingMemory,
        step: int,
    ) -> tuple[str, str, dict[str, Any] | None]:
        """Ask the LLM to produce the next Thought + Action + ActionInput."""

        user_message = (
            f"Step {step}/{self.max_steps}.\n\n"
            f"{memory.render_for_llm()}\n\n"
            "Respond with a single JSON object: "
            '{"thought": "...", "action": "...", "action_input": {...}}'
        )

        # Use the LLM with function-calling style if supported, else prompt-based
        raw = self.llm_service.agent_chat(
            system_prompt=system_prompt,
            user_message=user_message,
        )

        return self._parse_agent_response(raw)

    def _parse_agent_response(
        self, raw: str
    ) -> tuple[str, str, dict[str, Any] | None]:
        """Parse the LLM JSON response into (thought, action, action_input)."""
        try:
            data = extract_json(raw)
        except ValueError:
            raise AppError(
                f"Agent returned unparseable response: {raw[:300]}",
                status_code=502,
                code="agent_parse_error",
            )

        thought = str(data.get("thought", ""))
        action = str(data.get("action", "finish"))
        action_input = data.get("action_input")
        if isinstance(action_input, str):
            try:
                action_input = json.loads(action_input)
            except (json.JSONDecodeError, TypeError):
                action_input = {}
        return thought, action, action_input

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self, memory: WorkingMemory | None = None) -> str:
        tool_lines = []
        for tool in self.tool_registry.list_tools():
            params = json.dumps(tool.parameters_schema, ensure_ascii=False)
            tool_lines.append(f"- **{tool.name}**: {tool.description}\n  Parameters: {params}")
        tool_descriptions = "\n".join(tool_lines)
        prompt = AGENT_SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)
        if (
            memory is not None
            and memory.execution_plan is not None
            and memory.execution_plan.is_multi_step
        ):
            prompt += MULTI_STEP_PROMPT_ADDON
        return prompt

    def _update_memory_from_result(
        self,
        memory: WorkingMemory,
        tool_name: str,
        result: ToolResult,
    ) -> None:
        """Extract key data from tool results and store in memory shortcuts."""
        if not result.success:
            memory.record_error(result.error or "Tool call failed")
            return

        data = result.data
        if tool_name == "generate_selenium_script":
            memory.test_case_id = data.get("test_case_id")
            memory.current_code = data.get("generated_code")
        elif tool_name == "search_knowledge":
            memory.knowledge_context = data.get("context")
        elif tool_name == "repair_script":
            memory.current_code = data.get("repaired_code")
        elif tool_name == "execute_script":
            memory.execution_id = data.get("execution_id")
        elif tool_name == "get_execution_result":
            exec_status = data.get("status")
            if exec_status and exec_status not in ("completed", "healed_completed"):
                err = data.get("error") or data.get("logs") or ""
                if err:
                    memory.record_error(err[:1000])

    def _write_memory_cards(self, result: AgentRunResult) -> None:
        """Write success-pattern or known-trap memory cards based on run outcome."""
        if self._memory is None:
            return
        try:
            memory = result.memory
            prompt = memory.task_prompt
            execution_id = memory.execution_id or result.run_id

            # Count repair attempts (diagnose_failure calls indicate retries)
            repair_steps = sum(
                1 for a in memory.actions if a.tool_name == "repair_script"
            )

            if result.status == "success" and repair_steps == 0 and memory.current_code:
                self._memory.write_success_memory(
                    prompt=prompt,
                    code=memory.current_code,
                    execution_id=execution_id,
                )
                logger.info("Wrote success memory card for %s", execution_id)
            elif result.status in ("failed", "max_steps_reached"):
                error_summary = "\n".join(memory.accumulated_errors[-3:]) if memory.accumulated_errors else (result.error or "Unknown failure")
                self._memory.write_trap_memory(
                    prompt=prompt,
                    error_summary=error_summary,
                    execution_id=execution_id,
                    attempt_count=repair_steps + 1,
                )
                logger.info("Wrote trap memory card for %s", execution_id)
        except Exception:
            logger.warning("Failed to write memory card", exc_info=True)

    def _track_plan_step(
        self,
        memory: WorkingMemory,
        action: str,
        action_input: dict[str, Any] | None,
        tool_result: ToolResult,
        events: list[AgentEvent],
        step: int,
    ) -> None:
        """Record plan step progress when the agent indicates which plan step it's on."""
        if memory.execution_plan is None or not memory.execution_plan.is_multi_step:
            return

        plan_step_num = (action_input or {}).get("plan_step")
        if plan_step_num is None:
            return

        try:
            plan_step_num = int(plan_step_num)
        except (TypeError, ValueError):
            return

        # Find the matching plan step
        plan_step = None
        for ps in memory.execution_plan.steps:
            if ps.step_number == plan_step_num:
                plan_step = ps
                break

        status = "completed" if tool_result.success else "failed"
        step_result = {
            "step_number": plan_step_num,
            "action": plan_step.action if plan_step else action,
            "description": plan_step.description if plan_step else "",
            "status": status,
            "tool_used": action,
            "observation": tool_result.to_observation()[:500],
        }
        memory.step_results.append(step_result)

        events.append(AgentEvent(
            event_type="plan_step_complete",
            step=step,
            data=step_result,
        ))
        self._emit(events[-1])
        logger.info(
            "Plan step %d %s: %s",
            plan_step_num,
            status,
            plan_step.description if plan_step else "(unknown)",
        )

    def _emit(self, event: AgentEvent) -> None:
        if self._on_event is not None:
            try:
                self._on_event(event)
            except Exception:
                logger.warning("Event callback failed", exc_info=True)
