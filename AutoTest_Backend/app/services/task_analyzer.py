"""TaskAnalyzer: LLM-driven intent extraction and task decomposition.

Replaces the hardcoded keyword-matching in StrategyService with
structured LLM output for intent, complexity, steps, and success criteria.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import AppError
from app.utils.code_parser import extract_json

logger = logging.getLogger("autotest.task_analyzer")

# ---- Structured output schema sent to the LLM ----

TASK_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "login",
                "search",
                "navigate",
                "form_fill",
                "verify",
                "click",
                "multi_step",
                "other",
            ],
            "description": "The primary user intent.",
        },
        "target_site": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Target site URL if mentioned or inferrable.",
                },
                "name": {
                    "type": "string",
                    "description": "Human-readable site name (e.g. 'Baidu', 'vue-admin-template').",
                },
            },
        },
        "steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ordered list of expected user-facing steps.",
        },
        "preconditions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Conditions that must be true before the test starts.",
        },
        "success_criteria": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observable criteria to judge the test passed.",
        },
        "complexity": {
            "type": "string",
            "enum": ["simple", "multi_step", "complex_flow"],
            "description": "Task complexity level.",
        },
    },
    "required": ["intent", "steps", "success_criteria", "complexity"],
}

ANALYZER_SYSTEM_PROMPT = (
    "You are a test-scenario analyst. Given a natural-language description of a "
    "web UI test, output a JSON object that describes the task structure.\n\n"
    "JSON schema:\n"
    "{schema}\n\n"
    "Rules:\n"
    "- Respond with a single valid JSON object and nothing else.\n"
    "- `intent`: pick the most specific single intent.\n"
    "- `steps`: break the scenario into concrete UI steps (1-based).\n"
    "- `success_criteria`: what the test should assert after all steps.\n"
    "- `complexity`: 'simple' if ≤2 steps, 'multi_step' if 3-5, 'complex_flow' if >5.\n"
    "- If the target site URL is not explicitly mentioned, infer it from context or "
    "leave it empty.\n"
    "- Keep every value concise (under 120 characters per item).\n"
)


# ---- Data classes ----


@dataclass(frozen=True, slots=True)
class TargetSite:
    url: str = ""
    name: str = ""


@dataclass(frozen=True, slots=True)
class TaskAnalysis:
    """Structured result of analysing a user prompt."""

    intent: str
    target_site: TargetSite = field(default_factory=TargetSite)
    steps: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    complexity: str = "simple"
    raw_json: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "target_site": {"url": self.target_site.url, "name": self.target_site.name},
            "steps": self.steps,
            "preconditions": self.preconditions,
            "success_criteria": self.success_criteria,
            "complexity": self.complexity,
        }

    def to_prompt_block(self) -> str:
        """Render as a compact text block suitable for injection into LLM prompts."""
        lines = [
            f"Intent: {self.intent}",
            f"Complexity: {self.complexity}",
        ]
        if self.target_site.url:
            lines.append(f"Target URL: {self.target_site.url}")
        if self.target_site.name:
            lines.append(f"Target site: {self.target_site.name}")
        if self.steps:
            lines.append("Steps:")
            for i, s in enumerate(self.steps, 1):
                lines.append(f"  {i}. {s}")
        if self.preconditions:
            lines.append("Preconditions: " + "; ".join(self.preconditions))
        if self.success_criteria:
            lines.append("Success criteria: " + "; ".join(self.success_criteria))
        return "\n".join(lines)


# ---- Service ----


class TaskAnalyzer:
    """Analyse a user prompt using the LLM to produce a structured TaskAnalysis."""

    def __init__(self, llm_service) -> None:
        self._llm = llm_service

    def analyze(self, prompt: str) -> TaskAnalysis:
        """Send the prompt to the LLM and parse the structured JSON response."""
        system_prompt = ANALYZER_SYSTEM_PROMPT.format(
            schema=json.dumps(TASK_ANALYSIS_SCHEMA, ensure_ascii=False, indent=2),
        )

        try:
            raw = self._llm.agent_chat(
                system_prompt=system_prompt,
                user_message=prompt,
            )
        except Exception as exc:
            logger.warning("TaskAnalyzer LLM call failed, returning fallback: %s", exc)
            return self._fallback(prompt)

        return self._parse(raw, prompt)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self, raw: str, original_prompt: str) -> TaskAnalysis:
        """Parse the LLM JSON response into a TaskAnalysis."""
        try:
            data = extract_json(raw)
        except ValueError:
            logger.warning("TaskAnalyzer: unparseable LLM output, using fallback")
            return self._fallback(original_prompt)
        return self._build_from_dict(data)

    def _build_from_dict(self, data: dict[str, Any]) -> TaskAnalysis:
        """Construct a TaskAnalysis from a validated dict."""
        target_raw = data.get("target_site") or {}
        target_site = TargetSite(
            url=str(target_raw.get("url", "") or ""),
            name=str(target_raw.get("name", "") or ""),
        )

        intent = str(data.get("intent", "other"))
        complexity = str(data.get("complexity", "simple"))
        if complexity not in ("simple", "multi_step", "complex_flow"):
            complexity = "simple"

        steps = _str_list(data.get("steps"))
        preconditions = _str_list(data.get("preconditions"))
        success_criteria = _str_list(data.get("success_criteria"))

        return TaskAnalysis(
            intent=intent,
            target_site=target_site,
            steps=steps,
            preconditions=preconditions,
            success_criteria=success_criteria,
            complexity=complexity,
            raw_json=data,
        )

    # ------------------------------------------------------------------
    # Fallback (no LLM available or parse failure)
    # ------------------------------------------------------------------

    def _fallback(self, prompt: str) -> TaskAnalysis:
        """Best-effort heuristic when the LLM is unavailable."""
        intent = self._guess_intent(prompt)
        return TaskAnalysis(
            intent=intent,
            steps=[prompt[:200]],
            success_criteria=["Test Completed printed to stdout"],
            complexity="simple",
        )

    @staticmethod
    def _guess_intent(prompt: str) -> str:
        """Ultra-lightweight keyword fallback — only used when the LLM fails."""
        lower = prompt.lower()
        if any(kw in lower for kw in ("登录", "登入", "login", "sign in")):
            return "login"
        if any(kw in lower for kw in ("搜索", "搜寻", "检索", "search")):
            return "search"
        if any(kw in lower for kw in ("导航", "打开", "navigate", "open", "visit")):
            return "navigate"
        if any(kw in lower for kw in ("填写", "表单", "form", "fill")):
            return "form_fill"
        if any(kw in lower for kw in ("验证", "校验", "assert", "verify", "check")):
            return "verify"
        return "other"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------


def _str_list(value: Any) -> list[str]:
    """Coerce a value to list[str] safely."""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []
