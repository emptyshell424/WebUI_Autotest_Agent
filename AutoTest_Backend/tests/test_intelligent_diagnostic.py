"""Tests for IntelligentDiagnosticService: LLM diagnosis + regex fallback."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

from . import _bootstrap  # noqa: F401 — path bootstrap

from app.services.intelligent_diagnostic_service import (
    IntelligentDiagnosticService,
    IntelligentDiagnosis,
    FAILURE_TYPES_EXTENDED,
)
from app.services.failure_diagnostic_service import FailureDiagnosticService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_llm(response_dict: dict) -> MagicMock:
    llm = MagicMock()
    llm.agent_chat = MagicMock(return_value=json.dumps(response_dict, ensure_ascii=False))
    return llm


def _mock_llm_raw(raw: str) -> MagicMock:
    llm = MagicMock()
    llm.agent_chat = MagicMock(return_value=raw)
    return llm


# ---------------------------------------------------------------------------
# IntelligentDiagnosis data-class tests
# ---------------------------------------------------------------------------


class IntelligentDiagnosisTests(unittest.TestCase):
    def test_to_dict(self):
        d = IntelligentDiagnosis(
            failure_type="selector_not_found",
            failure_signal="NoSuchElementException",
            root_cause_analysis="The #kw element was not found.",
            repair_strategy="Use CSS selector input[name='wd'] instead.",
            confidence=0.85,
            suggested_selectors=["input[name='wd']", "#kw"],
            source="llm",
        )
        result = d.to_dict()
        self.assertEqual(result["failure_type"], "selector_not_found")
        self.assertEqual(result["confidence"], 0.85)
        self.assertEqual(len(result["suggested_selectors"]), 2)
        self.assertEqual(result["source"], "llm")

    def test_to_legacy(self):
        d = IntelligentDiagnosis(
            failure_type="wait_timeout",
            failure_signal="TimeoutException",
            root_cause_analysis="Page load was too slow.",
            repair_strategy="Increase wait time to 20s.",
            confidence=0.9,
            suggested_selectors=[],
            source="llm",
        )
        legacy = d.to_legacy()
        self.assertEqual(legacy.failure_type, "wait_timeout")
        self.assertEqual(legacy.failure_signal, "TimeoutException")
        self.assertEqual(legacy.suspected_root_cause, "Page load was too slow.")
        self.assertEqual(legacy.repair_hint, "Increase wait time to 20s.")


# ---------------------------------------------------------------------------
# LLM happy path
# ---------------------------------------------------------------------------


class IntelligentDiagnosticLLMTests(unittest.TestCase):
    def test_llm_diagnosis_high_confidence(self):
        response = {
            "failure_type": "selector_not_found",
            "failure_signal": "NoSuchElementException: Unable to locate element #login",
            "root_cause_analysis": "The login form uses id='loginForm' not '#login'.",
            "repair_strategy": "Replace #login with #loginForm.",
            "confidence": 0.9,
            "suggested_selectors": ["#loginForm", "form.login-container"],
        }
        svc = IntelligentDiagnosticService(llm_service=_mock_llm(response))
        result = svc.diagnose(
            error="NoSuchElementException: Unable to locate element #login",
            logs="Opening http://localhost:9528",
        )
        self.assertEqual(result.failure_type, "selector_not_found")
        self.assertEqual(result.source, "llm")
        self.assertGreaterEqual(result.confidence, 0.9)
        self.assertIn("#loginForm", result.suggested_selectors)

    def test_llm_diagnosis_with_code(self):
        response = {
            "failure_type": "wait_timeout",
            "failure_signal": "TimeoutException at line 15",
            "root_cause_analysis": "WebDriverWait timed out waiting for .el-table.",
            "repair_strategy": "Wait for loading mask to disappear first.",
            "confidence": 0.8,
        }
        svc = IntelligentDiagnosticService(llm_service=_mock_llm(response))
        result = svc.diagnose(
            error="TimeoutException",
            logs="Waiting for table",
            code="driver.find_element(By.CSS_SELECTOR, '.el-table')",
        )
        self.assertEqual(result.failure_type, "wait_timeout")
        self.assertEqual(result.source, "llm")

    def test_llm_diagnosis_with_fenced_json(self):
        fenced = '```json\n{"failure_type":"assertion_failed","failure_signal":"AssertionError","root_cause_analysis":"Title mismatch.","repair_strategy":"Fix the assertion.","confidence":0.7}\n```'
        svc = IntelligentDiagnosticService(llm_service=_mock_llm_raw(fenced))
        result = svc.diagnose(error="AssertionError")
        self.assertEqual(result.failure_type, "assertion_failed")
        self.assertEqual(result.source, "llm")


# ---------------------------------------------------------------------------
# Fallback to regex
# ---------------------------------------------------------------------------


class IntelligentDiagnosticFallbackTests(unittest.TestCase):
    def test_fallback_when_no_llm(self):
        svc = IntelligentDiagnosticService(llm_service=None)
        result = svc.diagnose(
            error="NoSuchElementException: Unable to locate element",
            logs="",
        )
        self.assertEqual(result.failure_type, "selector_not_found")
        self.assertEqual(result.source, "regex_fallback")

    def test_fallback_when_llm_raises(self):
        llm = MagicMock()
        llm.agent_chat = MagicMock(side_effect=RuntimeError("API down"))
        svc = IntelligentDiagnosticService(llm_service=llm)
        result = svc.diagnose(
            error="TimeoutException: Timed out",
            logs="",
        )
        self.assertEqual(result.failure_type, "wait_timeout")
        self.assertEqual(result.source, "regex_fallback")

    def test_fallback_when_llm_returns_garbage(self):
        svc = IntelligentDiagnosticService(llm_service=_mock_llm_raw("NOT JSON"))
        result = svc.diagnose(
            error="AssertionError: expected Dashboard",
            logs="",
        )
        self.assertEqual(result.failure_type, "assertion_failed")
        self.assertEqual(result.source, "regex_fallback")

    def test_fallback_when_confidence_below_threshold(self):
        response = {
            "failure_type": "navigation_error",
            "failure_signal": "unclear error",
            "root_cause_analysis": "Not sure what happened.",
            "repair_strategy": "Try again.",
            "confidence": 0.1,
        }
        svc = IntelligentDiagnosticService(
            llm_service=_mock_llm(response),
            confidence_threshold=0.3,
        )
        result = svc.diagnose(
            error="NoSuchElementException: Unable to locate",
            logs="",
        )
        # Should fallback to regex which detects selector_not_found
        self.assertEqual(result.failure_type, "selector_not_found")
        self.assertEqual(result.source, "regex_fallback")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class IntelligentDiagnosticEdgeCaseTests(unittest.TestCase):
    def test_unknown_failure_type_normalized(self):
        response = {
            "failure_type": "INVALID_TYPE",
            "failure_signal": "something",
            "root_cause_analysis": "unknown",
            "repair_strategy": "unknown",
            "confidence": 0.8,
        }
        svc = IntelligentDiagnosticService(llm_service=_mock_llm(response))
        result = svc.diagnose(error="some error")
        self.assertEqual(result.failure_type, "unknown_failure")
        self.assertEqual(result.source, "llm")

    def test_confidence_clamped(self):
        response = {
            "failure_type": "wait_timeout",
            "failure_signal": "timeout",
            "root_cause_analysis": "slow page",
            "repair_strategy": "wait more",
            "confidence": 5.0,  # out of range
        }
        svc = IntelligentDiagnosticService(llm_service=_mock_llm(response))
        result = svc.diagnose(error="timeout")
        self.assertLessEqual(result.confidence, 1.0)

    def test_no_error_provided(self):
        response = {
            "failure_type": "unknown_failure",
            "failure_signal": "No error details provided.",
            "root_cause_analysis": "Cannot diagnose without error info.",
            "repair_strategy": "Provide error details.",
            "confidence": 0.3,
        }
        svc = IntelligentDiagnosticService(llm_service=_mock_llm(response))
        result = svc.diagnose()
        self.assertEqual(result.failure_type, "unknown_failure")

    def test_all_extended_failure_types_accepted(self):
        for ft in FAILURE_TYPES_EXTENDED:
            response = {
                "failure_type": ft,
                "failure_signal": "sig",
                "root_cause_analysis": "cause",
                "repair_strategy": "fix",
                "confidence": 0.8,
            }
            svc = IntelligentDiagnosticService(llm_service=_mock_llm(response))
            result = svc.diagnose(error="test")
            self.assertEqual(result.failure_type, ft)


# ---------------------------------------------------------------------------
# Backward compatibility: legacy service still works standalone
# ---------------------------------------------------------------------------


class LegacyCompatTests(unittest.TestCase):
    def test_legacy_service_unchanged(self):
        legacy = FailureDiagnosticService()
        d = legacy.diagnose(
            error="NoSuchElementException: no such element",
            logs="",
        )
        self.assertEqual(d.failure_type, "selector_not_found")

    def test_intelligent_wraps_legacy_correctly(self):
        svc = IntelligentDiagnosticService(llm_service=None)
        result = svc.diagnose(
            error="blocked by safety validation",
            logs="",
            validation_errors=["import os is not allowed"],
        )
        self.assertEqual(result.failure_type, "safety_blocked")
        self.assertEqual(result.source, "regex_fallback")


if __name__ == "__main__":
    unittest.main()
