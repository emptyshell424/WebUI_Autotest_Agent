"""Tests for AdaptiveStrategyService."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from . import _bootstrap  # noqa: F401

from app.services.adaptive_strategy_service import (
    AdaptiveStrategyService,
    AdaptiveRepairDecision,
    REPAIR_APPROACH_SELECTOR_FIX,
    REPAIR_APPROACH_WAIT_ADJUST,
    REPAIR_APPROACH_FLOW_REDESIGN,
    REPAIR_APPROACH_ASSERTION_FIX,
    REPAIR_APPROACH_SAFETY_REWRITE,
    REPAIR_APPROACH_GENERAL,
)
from app.services.agent_memory_service import MemorySearchResult
from app.services.intelligent_diagnostic_service import IntelligentDiagnosis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_diag(failure_type: str = "selector_not_found", confidence: float = 0.9) -> MagicMock:
    svc = MagicMock()
    svc.diagnose.return_value = IntelligentDiagnosis(
        failure_type=failure_type,
        failure_signal="signal",
        root_cause_analysis="Root cause.",
        repair_strategy="Fix the selector.",
        confidence=confidence,
        suggested_selectors=["#kw", "input[name='wd']"],
        source="llm",
    )
    return svc


def _mock_memory(context: str = "", count: int = 0) -> MagicMock:
    svc = MagicMock()
    svc.search_similar.return_value = MemorySearchResult(
        cards=[{"content": context}] if count > 0 else [],
        context=context,
        result_count=count,
    )
    return svc


# ---------------------------------------------------------------------------
# Tests: approach selection
# ---------------------------------------------------------------------------


class ApproachSelectionTests(unittest.TestCase):
    """Verify the correct repair approach is selected per failure type."""

    def _select(self, failure_type: str) -> AdaptiveRepairDecision:
        diag = _mock_diag(failure_type=failure_type)
        svc = AdaptiveStrategyService(diagnostic_service=diag)
        return svc.select_strategy(error="some error", prompt="test")

    def test_selector_not_found(self):
        d = self._select("selector_not_found")
        self.assertEqual(d.approach, REPAIR_APPROACH_SELECTOR_FIX)

    def test_element_not_interactable(self):
        d = self._select("element_not_interactable")
        self.assertEqual(d.approach, REPAIR_APPROACH_SELECTOR_FIX)

    def test_wait_timeout(self):
        d = self._select("wait_timeout")
        self.assertEqual(d.approach, REPAIR_APPROACH_WAIT_ADJUST)

    def test_page_not_loaded(self):
        d = self._select("page_not_loaded")
        self.assertEqual(d.approach, REPAIR_APPROACH_WAIT_ADJUST)

    def test_assertion_failed(self):
        d = self._select("assertion_failed")
        self.assertEqual(d.approach, REPAIR_APPROACH_ASSERTION_FIX)

    def test_safety_blocked(self):
        d = self._select("safety_blocked")
        self.assertEqual(d.approach, REPAIR_APPROACH_SAFETY_REWRITE)

    def test_navigation_error(self):
        d = self._select("navigation_error")
        self.assertEqual(d.approach, REPAIR_APPROACH_FLOW_REDESIGN)

    def test_unknown_failure(self):
        d = self._select("unknown_failure")
        self.assertEqual(d.approach, REPAIR_APPROACH_GENERAL)

    def test_unrecognized_type_defaults_to_general(self):
        d = self._select("completely_new_type")
        self.assertEqual(d.approach, REPAIR_APPROACH_GENERAL)


# ---------------------------------------------------------------------------
# Tests: combined guidance
# ---------------------------------------------------------------------------


class CombinedGuidanceTests(unittest.TestCase):

    def test_guidance_contains_diagnosis_info(self):
        diag = _mock_diag(failure_type="wait_timeout")
        svc = AdaptiveStrategyService(diagnostic_service=diag)
        d = svc.select_strategy(error="timeout", prompt="test")

        self.assertIn("wait_timeout", d.combined_guidance)
        self.assertIn("Root cause", d.combined_guidance)
        self.assertIn("Fix the selector", d.combined_guidance)
        self.assertIn("Confidence", d.combined_guidance)

    def test_guidance_contains_suggested_selectors(self):
        diag = _mock_diag()
        svc = AdaptiveStrategyService(diagnostic_service=diag)
        d = svc.select_strategy(error="err", prompt="test")

        self.assertIn("#kw", d.combined_guidance)
        self.assertIn("input[name='wd']", d.combined_guidance)

    def test_guidance_contains_approach_text(self):
        diag = _mock_diag(failure_type="wait_timeout")
        svc = AdaptiveStrategyService(diagnostic_service=diag)
        d = svc.select_strategy(error="err", prompt="test")

        self.assertIn("wait_adjust", d.combined_guidance)
        self.assertIn("Increase WebDriverWait", d.combined_guidance)

    def test_guidance_includes_memory_when_available(self):
        diag = _mock_diag()
        memory = _mock_memory(context="# Past fix: use #su instead", count=1)
        svc = AdaptiveStrategyService(diagnostic_service=diag, memory_service=memory)
        d = svc.select_strategy(error="err", prompt="test")

        self.assertIn("Historical experience", d.combined_guidance)
        self.assertIn("use #su instead", d.combined_guidance)
        self.assertEqual(d.memory_hit_count, 1)

    def test_guidance_no_memory_section_when_empty(self):
        diag = _mock_diag()
        memory = _mock_memory(count=0)
        svc = AdaptiveStrategyService(diagnostic_service=diag, memory_service=memory)
        d = svc.select_strategy(error="err", prompt="test")

        self.assertNotIn("Historical experience", d.combined_guidance)
        self.assertEqual(d.memory_hit_count, 0)


# ---------------------------------------------------------------------------
# Tests: diagnosis integration
# ---------------------------------------------------------------------------


class DiagnosisIntegrationTests(unittest.TestCase):

    def test_diagnosis_is_forwarded(self):
        diag = _mock_diag(failure_type="assertion_failed", confidence=0.85)
        svc = AdaptiveStrategyService(diagnostic_service=diag)
        d = svc.select_strategy(error="AssertionError", prompt="check title")

        self.assertEqual(d.diagnosis.failure_type, "assertion_failed")
        self.assertAlmostEqual(d.diagnosis.confidence, 0.85)
        self.assertEqual(d.diagnosis.source, "llm")

    def test_no_diag_service_returns_unknown(self):
        svc = AdaptiveStrategyService(diagnostic_service=None)
        d = svc.select_strategy(error="boom", prompt="test")

        self.assertEqual(d.diagnosis.failure_type, "unknown_failure")
        self.assertAlmostEqual(d.diagnosis.confidence, 0.3)
        self.assertEqual(d.diagnosis.source, "none")

    def test_to_legacy_conversion(self):
        diag = _mock_diag(failure_type="wait_timeout")
        svc = AdaptiveStrategyService(diagnostic_service=diag)
        d = svc.select_strategy(error="timeout", prompt="test")

        legacy = d.diagnosis.to_legacy()
        self.assertEqual(legacy.failure_type, "wait_timeout")
        self.assertEqual(legacy.suspected_root_cause, "Root cause.")


# ---------------------------------------------------------------------------
# Tests: memory integration
# ---------------------------------------------------------------------------


class MemoryIntegrationTests(unittest.TestCase):

    def test_memory_searched_with_error_and_prompt(self):
        diag = _mock_diag()
        memory = _mock_memory(count=0)
        svc = AdaptiveStrategyService(diagnostic_service=diag, memory_service=memory)
        svc.select_strategy(error="NoSuchElement at #login", prompt="login to panel")

        memory.search_similar.assert_called_once()
        call_kwargs = memory.search_similar.call_args[1]
        self.assertIn("NoSuchElement", call_kwargs["query"])
        self.assertIn("login to panel", call_kwargs["query"])
        self.assertEqual(call_kwargs["card_type"], "heal")

    def test_memory_exception_graceful(self):
        diag = _mock_diag()
        memory = MagicMock()
        memory.search_similar.side_effect = RuntimeError("DB down")
        svc = AdaptiveStrategyService(diagnostic_service=diag, memory_service=memory)
        d = svc.select_strategy(error="err", prompt="test")

        self.assertEqual(d.memory_hit_count, 0)
        self.assertEqual(d.memory_context, "")

    def test_no_memory_service(self):
        diag = _mock_diag()
        svc = AdaptiveStrategyService(diagnostic_service=diag, memory_service=None)
        d = svc.select_strategy(error="err", prompt="test")

        self.assertEqual(d.memory_hit_count, 0)
        self.assertEqual(d.memory_context, "")


# ---------------------------------------------------------------------------
# Tests: to_dict
# ---------------------------------------------------------------------------


class ToDictTests(unittest.TestCase):

    def test_to_dict_contains_all_fields(self):
        diag = _mock_diag(failure_type="wait_timeout", confidence=0.75)
        memory = _mock_memory(context="past fix", count=2)
        svc = AdaptiveStrategyService(diagnostic_service=diag, memory_service=memory)
        d = svc.select_strategy(error="err", prompt="test")

        result = d.to_dict()
        self.assertEqual(result["approach"], REPAIR_APPROACH_WAIT_ADJUST)
        self.assertEqual(result["failure_type"], "wait_timeout")
        self.assertAlmostEqual(result["confidence"], 0.75)
        self.assertEqual(result["source"], "llm")
        self.assertEqual(result["memory_hit_count"], 2)


# ---------------------------------------------------------------------------
# Tests: RepairScriptTool with adaptive strategy
# ---------------------------------------------------------------------------


class RepairToolAdaptiveTests(unittest.TestCase):
    """Test that RepairScriptTool uses AdaptiveStrategyService when provided."""

    def _make_kwargs(self) -> dict:
        return {
            "prompt": "login test",
            "original_code": "driver.find_element(By.ID, 'login')",
            "error": "NoSuchElementException",
            "logs": "",
            "context": "",
        }

    def test_adaptive_used_when_provided(self):
        from app.tools.repair_tool import RepairScriptTool

        llm = MagicMock()
        llm.repair_script.return_value = "```python\nprint('fixed')\n```"

        adaptive = MagicMock()
        adaptive.select_strategy.return_value = AdaptiveRepairDecision(
            approach=REPAIR_APPROACH_SELECTOR_FIX,
            diagnosis=IntelligentDiagnosis(
                failure_type="selector_not_found",
                failure_signal="NoSuchElement",
                root_cause_analysis="Wrong ID.",
                repair_strategy="Try #loginForm.",
                confidence=0.9,
                suggested_selectors=["#loginForm"],
                source="llm",
            ),
            memory_context="# Past fix: use #loginForm",
            combined_guidance="Use #loginForm instead.",
            memory_hit_count=1,
        )

        tool = RepairScriptTool(llm, adaptive_strategy_service=adaptive)
        result = tool.execute(**self._make_kwargs())

        self.assertTrue(result.success)
        adaptive.select_strategy.assert_called_once()
        repair_call = llm.repair_script.call_args[1]
        self.assertIn("Use #loginForm", repair_call["repair_guidance"])
        self.assertEqual(repair_call["memory_context"], "# Past fix: use #loginForm")

    def test_fallback_to_legacy_without_adaptive(self):
        from app.tools.repair_tool import RepairScriptTool

        llm = MagicMock()
        llm.repair_script.return_value = "```python\nprint('fixed')\n```"

        tool = RepairScriptTool(llm, adaptive_strategy_service=None)
        result = tool.execute(**self._make_kwargs())

        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
