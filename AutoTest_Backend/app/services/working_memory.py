"""Working memory: per-task context window for the agent's ReAct loop."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.services.token_utils import (
    DEFAULT_CONTEXT_MAX_TOKENS,
    allocate_budget,
    estimate_tokens,
    truncate_to_tokens,
)

if TYPE_CHECKING:
    from app.services.planner import ExecutionPlan
    from app.services.task_analyzer import TaskAnalysis


@dataclass(slots=True)
class ActionRecord:
    """One step in the agent's Thought → Action → Observation cycle."""

    step: int
    thought: str
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    observation: str | None = None
    duration_ms: int = 0


@dataclass
class WorkingMemory:
    """Maintains the rolling context for a single agent task execution.

    Keeps token count bounded by summarising old steps when the window grows
    beyond *max_history_steps*.
    """

    task_prompt: str
    max_history_steps: int = 20
    max_token_budget: int = DEFAULT_CONTEXT_MAX_TOKENS
    actions: list[ActionRecord] = field(default_factory=list)
    current_code: str | None = None
    test_case_id: str | None = None
    execution_id: str | None = None
    knowledge_context: str | None = None
    accumulated_errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    task_analysis: TaskAnalysis | None = None
    execution_plan: ExecutionPlan | None = None
    step_results: list[dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_action(self, record: ActionRecord) -> None:
        self.actions.append(record)
        if len(self.actions) > self.max_history_steps:
            self._compact()

    def record_error(self, error: str) -> None:
        self.accumulated_errors.append(error[:2000])
        if len(self.accumulated_errors) > 10:
            self.accumulated_errors = self.accumulated_errors[-10:]

    # ------------------------------------------------------------------
    # Renderers (for LLM context injection)
    # ------------------------------------------------------------------

    def estimate_tokens(self) -> int:
        """Estimate total token count of all content currently in memory."""
        total = estimate_tokens(self.task_prompt)
        if self.task_analysis is not None:
            total += estimate_tokens(self.task_analysis.to_prompt_block())
        if self.execution_plan is not None:
            total += estimate_tokens(self.execution_plan.to_prompt_block())
        if self.knowledge_context:
            total += estimate_tokens(self.knowledge_context)
        if self.current_code:
            total += estimate_tokens(self.current_code)
        for err in self.accumulated_errors:
            total += estimate_tokens(err)
        for action in self.actions:
            total += estimate_tokens(action.thought)
            if action.observation:
                total += estimate_tokens(action.observation)
        return total

    def render_for_llm(self, max_tokens: int | None = None) -> str:
        """Build a compact textual summary suitable for the LLM system message.

        Uses priority-based budget allocation so that the most important
        sections (task prompt, analysis, plan) are always included while
        lower-priority sections (knowledge context, old action history) are
        truncated or dropped when the budget is tight.

        Priority levels (lower = kept first):
            1 — task prompt + task analysis
            2 — execution plan + step results
            3 — recent errors
            4 — current script
            5 — knowledge context
            6 — action history
        """
        budget = max_tokens if max_tokens is not None else self.max_token_budget

        # --- Build candidate sections ---
        sections: list[tuple[str, str, int]] = []

        # P1: Task prompt (always present)
        sections.append(("task", f"Task: {self.task_prompt}", 1))

        # P1: Task analysis
        if self.task_analysis is not None:
            sections.append(
                ("analysis", f"Task analysis:\n{self.task_analysis.to_prompt_block()}", 1)
            )

        # P2: Execution plan
        if self.execution_plan is not None:
            sections.append(
                ("plan", f"Execution plan:\n{self.execution_plan.to_prompt_block()}", 2)
            )

        # P2: Step results
        if self.step_results:
            sr_lines = []
            for sr in self.step_results[-5:]:
                status = sr.get("status", "unknown")
                desc = sr.get("description", "")[:120]
                sr_lines.append(f"  Step {sr.get('step_number', '?')}: [{status}] {desc}")
            sections.append(("step_results", "Plan step results:\n" + "\n".join(sr_lines), 2))

        # P3: Recent errors
        if self.accumulated_errors:
            err_text = "Recent errors:\n" + "\n".join(
                f"- {e[:300]}" for e in self.accumulated_errors[-3:]
            )
            sections.append(("errors", err_text, 3))

        # P4: Current script
        if self.current_code:
            code_preview = self.current_code[:3000]
            sections.append(
                ("code", f"Current script:\n```python\n{code_preview}\n```", 4)
            )

        # P5: Knowledge context
        if self.knowledge_context:
            sections.append(
                ("knowledge", f"Knowledge context: {self.knowledge_context}", 5)
            )

        # P6: Action history
        if self.actions:
            history_lines = ["Action history:"]
            for action in self.actions:
                line = f"  Step {action.step}: [Thought] {action.thought[:200]}"
                if action.tool_name:
                    line += f" → [Action] {action.tool_name}"
                if action.observation:
                    line += f" → [Observation] {action.observation[:300]}"
                history_lines.append(line)
            sections.append(("history", "\n".join(history_lines), 6))

        # --- Allocate budget and assemble ---
        allocated = allocate_budget(sections, budget)

        # Restore a deterministic output order matching the original rendering.
        order = ["task", "analysis", "plan", "step_results", "knowledge", "code", "errors", "history"]
        label_map = {label: text for label, text in allocated}
        parts = [label_map[k] for k in order if k in label_map]

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict for persistence and API responses."""
        return {
            "task_prompt": self.task_prompt,
            "test_case_id": self.test_case_id,
            "execution_id": self.execution_id,
            "step_count": len(self.actions),
            "current_code_lines": len(self.current_code.splitlines()) if self.current_code else 0,
            "accumulated_errors": self.accumulated_errors[-5:],
            "actions": [
                {
                    "step": a.step,
                    "thought": a.thought[:500],
                    "tool_name": a.tool_name,
                    "tool_input_keys": list((a.tool_input or {}).keys()),
                    "observation": (a.observation or "")[:500],
                    "duration_ms": a.duration_ms,
                }
                for a in self.actions
            ],
            "metadata": self.metadata,
            "task_analysis": self.task_analysis.to_dict() if self.task_analysis else None,
            "execution_plan": self.execution_plan.to_dict() if self.execution_plan else None,
            "step_results": self.step_results[-10:],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compact(self) -> None:
        """Summarise the oldest half of actions into a single entry.

        The observation snippet length is adaptive: when there are many old
        steps the per-step snippet is shorter to keep the summary under
        ~200 tokens.
        """
        mid = len(self.actions) // 2
        old = self.actions[:mid]
        # Adaptive snippet length: fewer chars when many steps are compacted.
        snippet_len = max(30, 120 // max(len(old), 1))
        summary_parts = []
        for a in old:
            brief = f"Step {a.step}: {a.tool_name or 'think'}"
            if a.observation:
                brief += f" → {a.observation[:snippet_len]}"
            summary_parts.append(brief)
        summary_text = "[Summary of earlier steps] " + " | ".join(summary_parts)
        # Hard-cap the summary to avoid degenerate growth.
        summary_text = truncate_to_tokens(summary_text, 200)
        summary_record = ActionRecord(
            step=0,
            thought=summary_text,
        )
        self.actions = [summary_record] + self.actions[mid:]
