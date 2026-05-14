"""AdaptiveStrategyService: combines diagnosis + memory → dynamic repair strategy.

Complements (does NOT replace) StrategyService by providing a general,
failure-type-driven approach to selecting repair tactics (selector fixes, wait
adjustments, flow redesign, etc.) for any failure scenario. StrategyService still
owns domain-specific strategy decisions like Baidu interaction_first vs result_first
downgrades. The two services cooperate: StrategyService decides the high-level
strategy (which page to interact with), AdaptiveStrategyService recommends the
low-level repair approach (how to fix the specific failure).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.agent_memory_service import AgentMemoryService, MemorySearchResult
from app.services.intelligent_diagnostic_service import IntelligentDiagnosticService, IntelligentDiagnosis

logger = logging.getLogger("autotest.adaptive_strategy")

# ---------------------------------------------------------------------------
# Repair approach definitions
# ---------------------------------------------------------------------------

REPAIR_APPROACH_SELECTOR_FIX = "selector_fix"
REPAIR_APPROACH_WAIT_ADJUST = "wait_adjust"
REPAIR_APPROACH_FLOW_REDESIGN = "flow_redesign"
REPAIR_APPROACH_ASSERTION_FIX = "assertion_fix"
REPAIR_APPROACH_SAFETY_REWRITE = "safety_rewrite"
REPAIR_APPROACH_GENERAL = "general"

# Maps failure types to default repair approaches
FAILURE_TYPE_TO_APPROACH = {
    "selector_not_found": REPAIR_APPROACH_SELECTOR_FIX,
    "element_not_interactable": REPAIR_APPROACH_SELECTOR_FIX,
    "wait_timeout": REPAIR_APPROACH_WAIT_ADJUST,
    "page_not_loaded": REPAIR_APPROACH_WAIT_ADJUST,
    "assertion_failed": REPAIR_APPROACH_ASSERTION_FIX,
    "safety_blocked": REPAIR_APPROACH_SAFETY_REWRITE,
    "navigation_error": REPAIR_APPROACH_FLOW_REDESIGN,
    "authentication_failed": REPAIR_APPROACH_FLOW_REDESIGN,
    "script_syntax_error": REPAIR_APPROACH_GENERAL,
    "unknown_failure": REPAIR_APPROACH_GENERAL,
}


@dataclass(frozen=True, slots=True)
class AdaptiveRepairDecision:
    """Result of the adaptive strategy selection."""

    approach: str
    diagnosis: IntelligentDiagnosis
    memory_context: str
    combined_guidance: str
    memory_hit_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "approach": self.approach,
            "failure_type": self.diagnosis.failure_type,
            "confidence": self.diagnosis.confidence,
            "source": self.diagnosis.source,
            "memory_hit_count": self.memory_hit_count,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AdaptiveStrategyService:
    """Selects repair strategy dynamically using diagnosis + memory.

    Usage:
        decision = adaptive.select_strategy(
            error="NoSuchElementException...",
            logs="...",
            code="...",
            prompt="打开百度搜索 Selenium",
        )
        # decision.combined_guidance → inject into repair prompt
        # decision.approach → for logging / metrics
    """

    def __init__(
        self,
        diagnostic_service: IntelligentDiagnosticService | None = None,
        memory_service: AgentMemoryService | None = None,
    ) -> None:
        self._diag = diagnostic_service
        self._memory = memory_service

    def select_strategy(
        self,
        *,
        error: str | None = None,
        logs: str | None = None,
        code: str | None = None,
        prompt: str = "",
        validation_errors: list[str] | None = None,
    ) -> AdaptiveRepairDecision:
        """Analyse the failure and return an adaptive repair decision."""

        # Step 1: intelligent diagnosis
        diagnosis = self._diagnose(
            error=error, logs=logs, code=code,
            validation_errors=validation_errors,
        )

        # Step 2: search memory for similar failures
        memory_result = self._search_memory(error=error, prompt=prompt)

        # Step 3: select repair approach
        approach = FAILURE_TYPE_TO_APPROACH.get(
            diagnosis.failure_type, REPAIR_APPROACH_GENERAL,
        )

        # Step 4: combine into guidance
        combined = self._build_combined_guidance(
            diagnosis=diagnosis,
            memory_result=memory_result,
            approach=approach,
        )

        logger.info(
            "Adaptive strategy: approach=%s failure_type=%s confidence=%.2f memory_hits=%d",
            approach, diagnosis.failure_type, diagnosis.confidence, memory_result.result_count,
        )

        return AdaptiveRepairDecision(
            approach=approach,
            diagnosis=diagnosis,
            memory_context=memory_result.context,
            combined_guidance=combined,
            memory_hit_count=memory_result.result_count,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _diagnose(
        self,
        *,
        error: str | None,
        logs: str | None,
        code: str | None,
        validation_errors: list[str] | None,
    ) -> IntelligentDiagnosis:
        if self._diag is None:
            return IntelligentDiagnosis(
                failure_type="unknown_failure",
                failure_signal=error[:200] if error else "",
                root_cause_analysis="No diagnostic service available.",
                repair_strategy="Apply general repair heuristics.",
                confidence=0.3,
                suggested_selectors=[],
                source="none",
            )
        return self._diag.diagnose(
            error=error, logs=logs, code=code,
            validation_errors=validation_errors,
        )

    def _search_memory(self, *, error: str | None, prompt: str) -> MemorySearchResult:
        if self._memory is None:
            return MemorySearchResult(cards=[], context="", result_count=0)
        try:
            query = f"failure: {(error or '')[:500]} scenario: {prompt[:300]}"
            return self._memory.search_similar(query=query, n_results=3, card_type="heal")
        except Exception:
            logger.warning("Memory search failed in adaptive strategy", exc_info=True)
            return MemorySearchResult(cards=[], context="", result_count=0)

    def _build_combined_guidance(
        self,
        *,
        diagnosis: IntelligentDiagnosis,
        memory_result: MemorySearchResult,
        approach: str,
    ) -> str:
        parts: list[str] = []

        # Diagnosis-based guidance
        parts.append(f"Failure type: {diagnosis.failure_type}")
        parts.append(f"Root cause: {diagnosis.root_cause_analysis}")
        parts.append(f"Repair strategy: {diagnosis.repair_strategy}")
        parts.append(f"Confidence: {diagnosis.confidence:.2f} (source: {diagnosis.source})")

        if diagnosis.suggested_selectors:
            parts.append("Suggested selectors: " + ", ".join(diagnosis.suggested_selectors[:5]))

        # Approach-specific guidance
        guidance = _APPROACH_GUIDANCE.get(approach, "")
        if guidance:
            parts.append(f"Approach ({approach}): {guidance}")

        # Memory-based guidance
        if memory_result.result_count > 0:
            parts.append(
                f"\nHistorical experience ({memory_result.result_count} similar case(s) found):\n"
                f"{memory_result.context[:3000]}"
            )

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Approach-specific general guidance templates
# ---------------------------------------------------------------------------

_APPROACH_GUIDANCE = {
    REPAIR_APPROACH_SELECTOR_FIX: (
        "The element selector is likely wrong or outdated. Try alternative selectors "
        "(CSS, XPath, name, class). Check if the element exists in the current DOM state. "
        "Consider adding a wait before the element lookup."
    ),
    REPAIR_APPROACH_WAIT_ADJUST: (
        "The page or element did not load in time. Increase WebDriverWait timeouts, "
        "add explicit waits for visibility/clickability, or wait for page load state."
    ),
    REPAIR_APPROACH_FLOW_REDESIGN: (
        "The interaction flow may need restructuring. Check if the navigation path "
        "is correct, if login credentials are valid, or if an intermediate page "
        "was skipped."
    ),
    REPAIR_APPROACH_ASSERTION_FIX: (
        "The assertion logic doesn't match the actual page state. Verify the expected "
        "text/element, check for dynamic content, and ensure the assertion runs after "
        "the page has fully rendered."
    ),
    REPAIR_APPROACH_SAFETY_REWRITE: (
        "The script uses disallowed imports or operations. Remove sys, os, pathlib, "
        "subprocess, and any non-Selenium imports. Rewrite using only Selenium APIs."
    ),
    REPAIR_APPROACH_GENERAL: (
        "Apply general repair heuristics: fix syntax errors, ensure imports are correct, "
        "add proper error handling, and verify the script logic matches the test intent."
    ),
}
