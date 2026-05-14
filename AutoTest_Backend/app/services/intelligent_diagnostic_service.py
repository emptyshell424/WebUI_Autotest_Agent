"""IntelligentDiagnosticService: LLM-driven semantic failure diagnosis.

Upgrades the regex-based FailureDiagnosticService with LLM semantic analysis.
Falls back to the legacy regex matcher when the LLM is unavailable or returns
low-confidence results.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.utils.code_parser import extract_json

from app.services.failure_diagnostic_service import (
    FailureDiagnosticService,
    FailureDiagnosis,
)

logger = logging.getLogger("autotest.intelligent_diagnostic")

# ---------------------------------------------------------------------------
# Extended diagnosis model
# ---------------------------------------------------------------------------

FAILURE_TYPES_EXTENDED = {
    "selector_not_found",
    "wait_timeout",
    "assertion_failed",
    "safety_blocked",
    "page_not_loaded",
    "element_not_interactable",
    "navigation_error",
    "script_syntax_error",
    "authentication_failed",
    "unknown_failure",
}


@dataclass(frozen=True, slots=True)
class IntelligentDiagnosis:
    """Extended diagnosis with LLM-derived fields."""

    failure_type: str
    failure_signal: str
    root_cause_analysis: str
    repair_strategy: str
    confidence: float  # 0.0 – 1.0
    suggested_selectors: list[str]
    source: str  # "llm" | "regex_fallback"

    def to_legacy(self) -> FailureDiagnosis:
        """Down-convert to the legacy FailureDiagnosis for backward compat."""
        return FailureDiagnosis(
            failure_type=self.failure_type,
            failure_signal=self.failure_signal,
            suspected_root_cause=self.root_cause_analysis,
            repair_hint=self.repair_strategy,
            suggested_selectors=list(self.suggested_selectors),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_type": self.failure_type,
            "failure_signal": self.failure_signal,
            "root_cause_analysis": self.root_cause_analysis,
            "repair_strategy": self.repair_strategy,
            "confidence": self.confidence,
            "suggested_selectors": self.suggested_selectors,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "failure_type": {
            "type": "string",
            "enum": sorted(FAILURE_TYPES_EXTENDED),
            "description": "Semantic failure category.",
        },
        "failure_signal": {
            "type": "string",
            "description": "The single most informative line from the error/logs.",
        },
        "root_cause_analysis": {
            "type": "string",
            "description": "Deep analysis of why this failure happened (2-3 sentences).",
        },
        "repair_strategy": {
            "type": "string",
            "description": "Concrete step-by-step repair instructions.",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "How confident you are in this diagnosis (0-1).",
        },
        "suggested_selectors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Alternative CSS/XPath selectors that might work.",
        },
    },
    "required": [
        "failure_type",
        "failure_signal",
        "root_cause_analysis",
        "repair_strategy",
        "confidence",
    ],
}

DIAGNOSIS_SYSTEM_PROMPT = (
    "You are a Selenium test failure analyst. Given the error output, stdout logs, "
    "and the failed script, produce a structured JSON diagnosis.\n\n"
    "JSON schema:\n{schema}\n\n"
    "Rules:\n"
    "- Respond with a single valid JSON object and nothing else.\n"
    "- `failure_type` must be one of the enum values.\n"
    "- `root_cause_analysis` should be specific to this failure, not generic.\n"
    "- `repair_strategy` should give actionable instructions the repair LLM can follow.\n"
    "- `confidence` should be low (<0.4) if the error is ambiguous.\n"
    "- `suggested_selectors` may be empty if not applicable.\n"
    "- Keep each string under 300 characters.\n"
)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class IntelligentDiagnosticService:
    """LLM-powered failure diagnosis with regex fallback."""

    def __init__(
        self,
        llm_service=None,
        legacy_service: FailureDiagnosticService | None = None,
        confidence_threshold: float = 0.3,
    ) -> None:
        self._llm = llm_service
        self._legacy = legacy_service or FailureDiagnosticService()
        self._confidence_threshold = confidence_threshold

    def diagnose(
        self,
        *,
        error: str | None = None,
        logs: str | None = None,
        code: str | None = None,
        validation_errors: list[str] | None = None,
    ) -> IntelligentDiagnosis:
        """Diagnose a failure using the LLM, falling back to regex on error."""
        # Safety violations are deterministic – skip LLM entirely.
        if validation_errors:
            return self._wrap_legacy(error=error, logs=logs, validation_errors=validation_errors)

        # If no LLM configured, go straight to legacy
        if self._llm is None:
            return self._wrap_legacy(error=error, logs=logs, validation_errors=validation_errors)

        try:
            result = self._llm_diagnose(error=error, logs=logs, code=code)
            if result.confidence >= self._confidence_threshold:
                return result
            logger.info(
                "LLM diagnosis confidence %.2f below threshold %.2f, using regex fallback",
                result.confidence,
                self._confidence_threshold,
            )
        except Exception:
            logger.warning("LLM diagnosis failed, using regex fallback", exc_info=True)

        return self._wrap_legacy(error=error, logs=logs, validation_errors=validation_errors)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_diagnose(
        self,
        *,
        error: str | None,
        logs: str | None,
        code: str | None,
    ) -> IntelligentDiagnosis:
        system_prompt = DIAGNOSIS_SYSTEM_PROMPT.format(
            schema=json.dumps(DIAGNOSIS_SCHEMA, ensure_ascii=False, indent=2),
        )
        user_parts = []
        if error:
            user_parts.append(f"Stderr / exception:\n{error[:3000]}")
        if logs:
            user_parts.append(f"Stdout logs:\n{logs[:2000]}")
        if code:
            user_parts.append(f"Failed script:\n```python\n{code[:4000]}\n```")
        if not user_parts:
            user_parts.append("No error details provided.")

        raw = self._llm.agent_chat(
            system_prompt=system_prompt,
            user_message="\n\n".join(user_parts),
        )
        return self._parse(raw)

    def _parse(self, raw: str) -> IntelligentDiagnosis:
        data = extract_json(raw)

        failure_type = str(data.get("failure_type", "unknown_failure"))
        if failure_type not in FAILURE_TYPES_EXTENDED:
            failure_type = "unknown_failure"

        confidence = data.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))

        suggested = data.get("suggested_selectors") or []
        if not isinstance(suggested, list):
            suggested = []

        return IntelligentDiagnosis(
            failure_type=failure_type,
            failure_signal=str(data.get("failure_signal", ""))[:500],
            root_cause_analysis=str(data.get("root_cause_analysis", ""))[:500],
            repair_strategy=str(data.get("repair_strategy", ""))[:500],
            confidence=confidence,
            suggested_selectors=[str(s) for s in suggested[:10]],
            source="llm",
        )

    # ------------------------------------------------------------------
    # Legacy fallback
    # ------------------------------------------------------------------

    def _wrap_legacy(
        self,
        *,
        error: str | None,
        logs: str | None,
        validation_errors: list[str] | None = None,
    ) -> IntelligentDiagnosis:
        legacy = self._legacy.diagnose(
            error=error,
            logs=logs,
            validation_errors=validation_errors,
        )
        return IntelligentDiagnosis(
            failure_type=legacy.failure_type,
            failure_signal=legacy.failure_signal,
            root_cause_analysis=legacy.suspected_root_cause,
            repair_strategy=legacy.repair_hint,
            confidence=0.6,
            suggested_selectors=[],
            source="regex_fallback",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
