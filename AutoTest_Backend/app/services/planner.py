"""Planner: LLM-driven task decomposition into an executable step plan.

Given a TaskAnalysis, the Planner produces an ExecutionPlan — a structured
sequence of PlanStep objects that the AgentOrchestrator can execute one by one,
injecting each step's result into the next step's context.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.utils.code_parser import extract_json, strip_fences as _strip_fences

logger = logging.getLogger("autotest.planner")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlanStep:
    """A single step inside an execution plan."""

    step_number: int
    action: str  # e.g. "navigate", "login", "click", "verify", "search", "wait", "fill_form"
    description: str  # human-readable description of what this step does
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)  # step_numbers this step depends on

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "description": self.description,
            "parameters": self.parameters,
            "depends_on": self.depends_on,
        }


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """A complete execution plan produced by the Planner."""

    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    estimated_complexity: str = "simple"  # simple | multi_step | complex_flow
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def is_multi_step(self) -> bool:
        return len(self.steps) > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "estimated_complexity": self.estimated_complexity,
            "step_count": self.step_count,
            "metadata": self.metadata,
        }

    def to_prompt_block(self) -> str:
        """Render the plan as a compact text block for LLM context injection."""
        lines = [
            f"Execution Plan ({self.estimated_complexity}, {self.step_count} steps):",
            f"Goal: {self.goal}",
        ]
        for s in self.steps:
            dep = f" (after step {', '.join(map(str, s.depends_on))})" if s.depends_on else ""
            params = f" | params: {json.dumps(s.parameters, ensure_ascii=False)}" if s.parameters else ""
            lines.append(f"  {s.step_number}. [{s.action}] {s.description}{dep}{params}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

PLAN_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {
            "type": "string",
            "description": "One-sentence summary of the overall test goal.",
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer"},
                    "action": {
                        "type": "string",
                        "enum": [
                            "navigate",
                            "login",
                            "click",
                            "fill_form",
                            "search",
                            "wait",
                            "verify",
                            "scroll",
                            "select",
                            "hover",
                            "custom",
                        ],
                    },
                    "description": {"type": "string"},
                    "parameters": {"type": "object"},
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["step_number", "action", "description"],
            },
        },
        "estimated_complexity": {
            "type": "string",
            "enum": ["simple", "multi_step", "complex_flow"],
        },
    },
    "required": ["goal", "steps", "estimated_complexity"],
}

PLANNER_SYSTEM_PROMPT = (
    "You are a test execution planner. Given a structured task analysis of a "
    "web UI test, produce a detailed step-by-step execution plan.\n\n"
    "JSON schema for your output:\n"
    "{schema}\n\n"
    "Rules:\n"
    "- Respond with a single valid JSON object and nothing else.\n"
    "- Each step must be a concrete, atomic UI action.\n"
    "- step_number starts at 1 and increments sequentially.\n"
    "- depends_on lists step_numbers that must complete before this step can run "
    "(default: previous step).\n"
    "- parameters should contain key details (url, selector, text, credentials, etc.).\n"
    "- estimated_complexity: 'simple' if ≤2 steps, 'multi_step' if 3-5, "
    "'complex_flow' if >5.\n"
    "- Always end with a 'verify' step that checks the test's success criteria.\n"
    "- Keep descriptions concise (under 120 characters).\n"
)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class Planner:
    """Produce an ExecutionPlan from a TaskAnalysis using the LLM."""

    def __init__(self, llm_service) -> None:
        self._llm = llm_service

    def plan(self, task_analysis) -> ExecutionPlan:
        """Generate an execution plan for the given TaskAnalysis.

        Falls back to a simple single-step plan if the LLM call fails.
        """
        # For simple tasks, skip the LLM call and build a trivial plan directly
        if task_analysis.complexity == "simple" and len(task_analysis.steps) <= 2:
            return self._build_simple_plan(task_analysis)

        system_prompt = PLANNER_SYSTEM_PROMPT.format(
            schema=json.dumps(PLAN_OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
        )
        user_message = (
            "Task analysis:\n"
            f"{task_analysis.to_prompt_block()}\n\n"
            "Produce an execution plan."
        )

        try:
            raw = self._llm.agent_chat(
                system_prompt=system_prompt,
                user_message=user_message,
            )
        except Exception as exc:
            logger.warning("Planner LLM call failed, returning fallback: %s", exc)
            return self._fallback(task_analysis)

        return self._parse(raw, task_analysis)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self, raw: str, task_analysis) -> ExecutionPlan:
        """Parse the LLM JSON response into an ExecutionPlan."""
        try:
            data = extract_json(raw)
        except ValueError:
            logger.warning("Planner: unparseable LLM output, using fallback")
            return self._fallback(task_analysis)
        return self._build_from_dict(data, task_analysis)

    def _build_from_dict(self, data: dict[str, Any], task_analysis) -> ExecutionPlan:
        """Construct an ExecutionPlan from a validated dict."""
        goal = str(data.get("goal", task_analysis.steps[0] if task_analysis.steps else "Execute test"))
        complexity = str(data.get("estimated_complexity", task_analysis.complexity))
        if complexity not in ("simple", "multi_step", "complex_flow"):
            complexity = task_analysis.complexity

        raw_steps = data.get("steps") or []
        if not isinstance(raw_steps, list):
            raw_steps = []

        steps: list[PlanStep] = []
        for i, s in enumerate(raw_steps):
            if not isinstance(s, dict):
                continue
            step_number = int(s.get("step_number", i + 1))
            action = str(s.get("action", "custom"))
            description = str(s.get("description", ""))
            parameters = s.get("parameters") if isinstance(s.get("parameters"), dict) else {}
            depends_raw = s.get("depends_on") or []
            depends_on = [int(d) for d in depends_raw if isinstance(d, (int, float))]
            steps.append(PlanStep(
                step_number=step_number,
                action=action,
                description=description,
                parameters=parameters,
                depends_on=depends_on,
            ))

        if not steps:
            return self._fallback(task_analysis)

        return ExecutionPlan(
            goal=goal,
            steps=steps,
            estimated_complexity=complexity,
        )

    # ------------------------------------------------------------------
    # Fallback / simple plan
    # ------------------------------------------------------------------

    def _fallback(self, task_analysis) -> ExecutionPlan:
        """Build a minimal plan from the TaskAnalysis steps when LLM fails."""
        return self._build_simple_plan(task_analysis)

    def _build_simple_plan(self, task_analysis) -> ExecutionPlan:
        """Construct a plan directly from TaskAnalysis without an LLM call."""
        steps: list[PlanStep] = []
        ta_steps = task_analysis.steps if task_analysis.steps else [task_analysis.intent]

        for i, step_desc in enumerate(ta_steps, 1):
            action = _infer_action(step_desc, task_analysis.intent)
            deps = [i - 1] if i > 1 else []
            steps.append(PlanStep(
                step_number=i,
                action=action,
                description=step_desc,
                depends_on=deps,
            ))

        # Ensure a verify step exists at the end
        if steps and steps[-1].action != "verify":
            criteria = (
                task_analysis.success_criteria[0]
                if task_analysis.success_criteria
                else "Verify test completed successfully"
            )
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                action="verify",
                description=criteria,
                depends_on=[len(steps)],
            ))

        return ExecutionPlan(
            goal=ta_steps[0] if ta_steps else task_analysis.intent,
            steps=steps,
            estimated_complexity=task_analysis.complexity,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_action(step_description: str, intent: str) -> str:
    """Best-effort mapping from a step description to an action category."""
    lower = step_description.lower()
    if any(kw in lower for kw in ("navigate", "open", "go to", "visit", "打开", "访问", "导航")):
        return "navigate"
    if any(kw in lower for kw in ("login", "sign in", "登录", "登入", "credentials")):
        return "login"
    if any(kw in lower for kw in ("click", "press", "tap", "点击", "按下")):
        return "click"
    if any(kw in lower for kw in ("fill", "type", "enter", "input", "填写", "输入")):
        return "fill_form"
    if any(kw in lower for kw in ("search", "搜索", "检索", "查找")):
        return "search"
    if any(kw in lower for kw in ("wait", "等待", "delay")):
        return "wait"
    if any(kw in lower for kw in ("verify", "assert", "check", "confirm", "验证", "校验", "确认")):
        return "verify"
    if any(kw in lower for kw in ("scroll", "滚动")):
        return "scroll"
    if any(kw in lower for kw in ("select", "choose", "dropdown", "选择", "下拉")):
        return "select"
    if any(kw in lower for kw in ("hover", "悬停", "mouse over")):
        return "hover"
    # Default: use intent as a reasonable fallback
    if intent in ("login", "search", "navigate", "verify", "click", "form_fill"):
        return intent if intent != "form_fill" else "fill_form"
    return "custom"
