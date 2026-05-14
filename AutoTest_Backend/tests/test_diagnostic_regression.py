"""Regression tests: IntelligentDiagnosticService >= FailureDiagnosticService.

Verifies that the new LLM-driven diagnostic (with regex fallback) classifies
a standard set of failure scenarios at least as well as the legacy regex-only
diagnostic.  Two test groups:

1. **Fallback parity** – IntelligentDiagnosticService with *no* LLM must
   produce the exact same failure_type as FailureDiagnosticService for every
   scenario (they share the same regex engine).

2. **LLM-path coverage** – With a mock LLM that returns valid JSON, the new
   service should classify every scenario into a *non-unknown* type at least
   as often as the regex baseline.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass
from typing import List
from unittest.mock import MagicMock

from . import _bootstrap  # noqa: F401

from app.services.failure_diagnostic_service import (
    FailureDiagnosticService,
    FailureDiagnosis,
)
from app.services.intelligent_diagnostic_service import (
    IntelligentDiagnosticService,
    IntelligentDiagnosis,
    FAILURE_TYPES_EXTENDED,
)


# ---------------------------------------------------------------------------
# Scenario catalogue
# ---------------------------------------------------------------------------

@dataclass
class FailureScenario:
    """One failure scenario with its expected regex classification."""
    name: str
    error: str | None
    logs: str | None
    validation_errors: list[str] | None
    expected_type: str  # expected regex-based failure_type


SCENARIOS: List[FailureScenario] = [
    # --- selector_not_found ---
    FailureScenario(
        name="NoSuchElementException",
        error="selenium.common.exceptions.NoSuchElementException: Message: no such element: Unable to locate element: {\"method\":\"css selector\",\"selector\":\"#kw\"}",
        logs=None,
        validation_errors=None,
        expected_type="selector_not_found",
    ),
    FailureScenario(
        name="unable_to_locate_element",
        error="Unable to locate element with css selector '#missing-btn'",
        logs=None,
        validation_errors=None,
        expected_type="selector_not_found",
    ),
    FailureScenario(
        name="could_not_locate",
        error="could not locate element by id='submit'",
        logs="INFO: navigated to page\n",
        validation_errors=None,
        expected_type="selector_not_found",
    ),
    FailureScenario(
        name="cannot_locate_element",
        error="cannot locate element using xpath //button[@class='login']",
        logs=None,
        validation_errors=None,
        expected_type="selector_not_found",
    ),
    FailureScenario(
        name="find_element_failure",
        error="driver.find_element raised an error for selector 'div.content'",
        logs=None,
        validation_errors=None,
        expected_type="selector_not_found",
    ),

    # --- wait_timeout ---
    FailureScenario(
        name="TimeoutException",
        error="selenium.common.exceptions.TimeoutException: Message: timed out after 10s waiting for visibility of element",
        logs=None,
        validation_errors=None,
        expected_type="wait_timeout",
    ),
    FailureScenario(
        name="execution_timed_out",
        error="execution timed out after 30 seconds",
        logs=None,
        validation_errors=None,
        expected_type="wait_timeout",
    ),
    FailureScenario(
        name="waiting_for_condition",
        error="Error: timeout while waiting for page load",
        logs="waiting for element to become clickable",
        validation_errors=None,
        expected_type="wait_timeout",
    ),
    FailureScenario(
        name="wait_until_condition",
        error="wait until condition not met within timeout",
        logs=None,
        validation_errors=None,
        expected_type="wait_timeout",
    ),

    # --- assertion_failed ---
    FailureScenario(
        name="AssertionError",
        error="AssertionError: expected title 'Dashboard' but got 'Login'",
        logs=None,
        validation_errors=None,
        expected_type="assertion_failed",
    ),
    FailureScenario(
        name="assert_failed_keyword",
        error="assert failed: element text did not match",
        logs=None,
        validation_errors=None,
        expected_type="assertion_failed",
    ),
    FailureScenario(
        name="expected_actual_mismatch",
        error="expected 'OK' but actual was 'Error'",
        logs=None,
        validation_errors=None,
        expected_type="assertion_failed",
    ),

    # --- safety_blocked ---
    FailureScenario(
        name="safety_validation_blocked",
        error="Blocked by safety validation: import os is not allowed",
        logs=None,
        validation_errors=None,
        expected_type="safety_blocked",
    ),
    FailureScenario(
        name="validation_errors_list",
        error=None,
        logs=None,
        validation_errors=["import subprocess is not allowed", "open() call is not allowed"],
        expected_type="safety_blocked",
    ),
    FailureScenario(
        name="is_not_allowed",
        error="exec() is not allowed by the safety policy",
        logs=None,
        validation_errors=None,
        expected_type="safety_blocked",
    ),

    # --- unknown_failure ---
    FailureScenario(
        name="generic_python_error",
        error="ZeroDivisionError: division by zero",
        logs=None,
        validation_errors=None,
        expected_type="unknown_failure",
    ),
    FailureScenario(
        name="empty_error",
        error="",
        logs="",
        validation_errors=None,
        expected_type="unknown_failure",
    ),
]


# ---------------------------------------------------------------------------
# Mock LLM that returns a plausible JSON diagnosis for any input
# ---------------------------------------------------------------------------

def _build_llm_mock(failure_type: str = "selector_not_found") -> MagicMock:
    """Return a mock LLM whose agent_chat always returns valid diagnosis JSON."""
    llm = MagicMock()

    def _agent_chat(*, system_prompt: str, user_message: str) -> str:
        # Heuristic: derive a reasonable failure_type from the user message
        msg = user_message.lower()
        ft = "unknown_failure"
        if any(k in msg for k in ("no such element", "locate element", "find_element", "cannot locate")):
            ft = "selector_not_found"
        elif any(k in msg for k in ("timeout", "timed out", "waiting for", "wait until")):
            ft = "wait_timeout"
        elif any(k in msg for k in ("assertionerror", "assert ", "expected", "actual")):
            ft = "assertion_failed"
        elif any(k in msg for k in ("safety", "blocked", "not allowed")):
            ft = "safety_blocked"
        elif any(k in msg for k in ("page_not_loaded", "net::err", "page load")):
            ft = "page_not_loaded"
        elif any(k in msg for k in ("not interactable", "element not interactable")):
            ft = "element_not_interactable"
        elif any(k in msg for k in ("syntaxerror", "syntax error")):
            ft = "script_syntax_error"

        return json.dumps({
            "failure_type": ft,
            "failure_signal": "mock signal",
            "root_cause_analysis": "Mock root cause.",
            "repair_strategy": "Mock repair strategy.",
            "confidence": 0.85,
            "suggested_selectors": [],
        })

    llm.agent_chat = _agent_chat
    return llm


# ---------------------------------------------------------------------------
# Test group 1: Fallback parity (no LLM → pure regex)
# ---------------------------------------------------------------------------

class FallbackParityTests(unittest.TestCase):
    """IntelligentDiagnosticService with no LLM must match FailureDiagnosticService."""

    def setUp(self):
        self.legacy = FailureDiagnosticService()
        self.intelligent = IntelligentDiagnosticService(llm_service=None)

    def _run_scenario(self, scenario: FailureScenario):
        legacy_result = self.legacy.diagnose(
            error=scenario.error,
            logs=scenario.logs,
            validation_errors=scenario.validation_errors,
        )
        intel_result = self.intelligent.diagnose(
            error=scenario.error,
            logs=scenario.logs,
            validation_errors=scenario.validation_errors,
        )
        self.assertEqual(
            intel_result.failure_type,
            legacy_result.failure_type,
            f"Scenario '{scenario.name}': intelligent fallback type "
            f"'{intel_result.failure_type}' != legacy type '{legacy_result.failure_type}'",
        )
        self.assertEqual(intel_result.source, "regex_fallback")
        # failure_type must also match the expected catalogue value
        self.assertEqual(
            legacy_result.failure_type,
            scenario.expected_type,
            f"Scenario '{scenario.name}': legacy type '{legacy_result.failure_type}' "
            f"!= expected '{scenario.expected_type}'",
        )


# Dynamically generate one test method per scenario for clear reporting.
def _add_parity_test(scenario: FailureScenario):
    def test_method(self):
        self._run_scenario(scenario)
    test_method.__doc__ = f"Fallback parity – {scenario.name}"
    setattr(FallbackParityTests, f"test_{scenario.name}", test_method)


for _sc in SCENARIOS:
    _add_parity_test(_sc)


# ---------------------------------------------------------------------------
# Test group 2: LLM-path coverage ≥ regex baseline
# ---------------------------------------------------------------------------

class LLMCoverageTests(unittest.TestCase):
    """With a mock LLM, IntelligentDiagnosticService should classify at
    least as many scenarios into non-unknown types as the regex baseline."""

    def setUp(self):
        self.legacy = FailureDiagnosticService()
        self.intelligent = IntelligentDiagnosticService(
            llm_service=_build_llm_mock(),
            confidence_threshold=0.3,
        )

    def test_coverage_gte_legacy(self):
        """LLM-path non-unknown coverage ≥ regex non-unknown coverage."""
        legacy_non_unknown = 0
        intel_non_unknown = 0

        for sc in SCENARIOS:
            legacy_res = self.legacy.diagnose(
                error=sc.error,
                logs=sc.logs,
                validation_errors=sc.validation_errors,
            )
            intel_res = self.intelligent.diagnose(
                error=sc.error,
                logs=sc.logs,
                code=None,
                validation_errors=sc.validation_errors,
            )
            if legacy_res.failure_type != "unknown_failure":
                legacy_non_unknown += 1
            if intel_res.failure_type != "unknown_failure":
                intel_non_unknown += 1

        self.assertGreaterEqual(
            intel_non_unknown,
            legacy_non_unknown,
            f"LLM coverage ({intel_non_unknown}) < regex coverage ({legacy_non_unknown})",
        )

    def test_llm_path_all_known_scenarios_non_unknown(self):
        """For scenarios whose expected_type is not unknown_failure, the LLM
        path should also produce a non-unknown result."""
        for sc in SCENARIOS:
            if sc.expected_type == "unknown_failure":
                continue
            intel_res = self.intelligent.diagnose(
                error=sc.error,
                logs=sc.logs,
                code=None,
                validation_errors=sc.validation_errors,
            )
            self.assertNotEqual(
                intel_res.failure_type,
                "unknown_failure",
                f"Scenario '{sc.name}': LLM path unexpectedly returned unknown_failure",
            )

    def test_llm_source_when_confident(self):
        """When the mock LLM returns confidence ≥ threshold, source should be 'llm'."""
        # Use a scenario with clear signal so mock LLM returns high confidence
        sc = SCENARIOS[0]  # NoSuchElementException
        result = self.intelligent.diagnose(
            error=sc.error,
            logs=sc.logs,
            code="driver.find_element(...)",
            validation_errors=sc.validation_errors,
        )
        self.assertEqual(result.source, "llm")
        self.assertGreaterEqual(result.confidence, 0.3)


# ---------------------------------------------------------------------------
# Test group 3: Extended failure types (LLM-only categories)
# ---------------------------------------------------------------------------

class ExtendedTypeTests(unittest.TestCase):
    """Verify that the LLM path can produce extended failure types that the
    regex path cannot (page_not_loaded, element_not_interactable, etc.)."""

    def _make_service(self, forced_type: str, confidence: float = 0.9) -> IntelligentDiagnosticService:
        llm = MagicMock()
        llm.agent_chat.return_value = json.dumps({
            "failure_type": forced_type,
            "failure_signal": "mock signal",
            "root_cause_analysis": "analysis",
            "repair_strategy": "strategy",
            "confidence": confidence,
            "suggested_selectors": [],
        })
        return IntelligentDiagnosticService(llm_service=llm, confidence_threshold=0.3)

    def test_page_not_loaded(self):
        svc = self._make_service("page_not_loaded")
        res = svc.diagnose(error="net::ERR_CONNECTION_REFUSED")
        self.assertEqual(res.failure_type, "page_not_loaded")
        self.assertEqual(res.source, "llm")

    def test_element_not_interactable(self):
        svc = self._make_service("element_not_interactable")
        res = svc.diagnose(error="ElementNotInteractableException")
        self.assertEqual(res.failure_type, "element_not_interactable")

    def test_navigation_error(self):
        svc = self._make_service("navigation_error")
        res = svc.diagnose(error="invalid URL, navigation failed")
        self.assertEqual(res.failure_type, "navigation_error")

    def test_script_syntax_error(self):
        svc = self._make_service("script_syntax_error")
        res = svc.diagnose(error="SyntaxError: invalid syntax line 12")
        self.assertEqual(res.failure_type, "script_syntax_error")

    def test_authentication_failed(self):
        svc = self._make_service("authentication_failed")
        res = svc.diagnose(error="Login rejected: invalid credentials")
        self.assertEqual(res.failure_type, "authentication_failed")

    def test_unknown_type_normalized(self):
        """If the LLM returns a type not in the enum, it should be normalized to unknown_failure."""
        svc = self._make_service("totally_made_up_type")
        res = svc.diagnose(error="something")
        self.assertEqual(res.failure_type, "unknown_failure")


# ---------------------------------------------------------------------------
# Test group 4: Fallback on LLM failure / low-confidence
# ---------------------------------------------------------------------------

class FallbackBehaviorTests(unittest.TestCase):
    """Verify graceful degradation to regex when LLM fails or is low-confidence."""

    def test_fallback_on_llm_exception(self):
        llm = MagicMock()
        llm.agent_chat.side_effect = RuntimeError("LLM unreachable")
        svc = IntelligentDiagnosticService(llm_service=llm)
        res = svc.diagnose(error="NoSuchElementException: unable to locate element")
        self.assertEqual(res.failure_type, "selector_not_found")
        self.assertEqual(res.source, "regex_fallback")

    def test_fallback_on_low_confidence(self):
        llm = MagicMock()
        llm.agent_chat.return_value = json.dumps({
            "failure_type": "page_not_loaded",
            "failure_signal": "sig",
            "root_cause_analysis": "cause",
            "repair_strategy": "fix",
            "confidence": 0.1,  # below default threshold 0.3
            "suggested_selectors": [],
        })
        svc = IntelligentDiagnosticService(llm_service=llm, confidence_threshold=0.3)
        res = svc.diagnose(error="TimeoutException: timed out")
        self.assertEqual(res.failure_type, "wait_timeout")
        self.assertEqual(res.source, "regex_fallback")

    def test_fallback_on_invalid_json(self):
        llm = MagicMock()
        llm.agent_chat.return_value = "This is not JSON at all."
        svc = IntelligentDiagnosticService(llm_service=llm)
        res = svc.diagnose(
            error="Blocked by safety validation: import os",
            validation_errors=["import os is not allowed"],
        )
        self.assertEqual(res.failure_type, "safety_blocked")
        self.assertEqual(res.source, "regex_fallback")

    def test_no_llm_always_regex(self):
        svc = IntelligentDiagnosticService(llm_service=None)
        for sc in SCENARIOS:
            res = svc.diagnose(
                error=sc.error,
                logs=sc.logs,
                validation_errors=sc.validation_errors,
            )
            self.assertEqual(res.source, "regex_fallback",
                             f"Scenario '{sc.name}' should always be regex_fallback")


# ---------------------------------------------------------------------------
# Test group 5: to_legacy() backward compatibility
# ---------------------------------------------------------------------------

class LegacyCompatTests(unittest.TestCase):
    """IntelligentDiagnosis.to_legacy() should produce a valid FailureDiagnosis."""

    def test_to_legacy_round_trip(self):
        diag = IntelligentDiagnosis(
            failure_type="wait_timeout",
            failure_signal="timed out",
            root_cause_analysis="Page slow.",
            repair_strategy="Add explicit wait.",
            confidence=0.9,
            suggested_selectors=["#el"],
            source="llm",
        )
        legacy = diag.to_legacy()
        self.assertIsInstance(legacy, FailureDiagnosis)
        self.assertEqual(legacy.failure_type, "wait_timeout")
        self.assertEqual(legacy.failure_signal, "timed out")
        self.assertEqual(legacy.suspected_root_cause, "Page slow.")
        self.assertEqual(legacy.repair_hint, "Add explicit wait.")

    def test_to_dict_has_all_fields(self):
        diag = IntelligentDiagnosis(
            failure_type="assertion_failed",
            failure_signal="AssertionError",
            root_cause_analysis="Wrong title.",
            repair_strategy="Fix assertion.",
            confidence=0.75,
            suggested_selectors=[],
            source="llm",
        )
        d = diag.to_dict()
        self.assertIn("failure_type", d)
        self.assertIn("confidence", d)
        self.assertIn("source", d)
        self.assertEqual(d["failure_type"], "assertion_failed")
        self.assertEqual(d["source"], "llm")


if __name__ == "__main__":
    unittest.main()
