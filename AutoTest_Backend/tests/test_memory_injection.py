"""Tests for memory injection into repair flow."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from . import _bootstrap  # noqa: F401

from app.services.agent_memory_service import MemorySearchResult
from app.services.site_profile_service import SiteProfile, SiteProfileService
from app.tools.repair_tool import RepairScriptTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_llm(repaired_code: str = "print('repaired')") -> MagicMock:
    llm = MagicMock()
    llm.repair_script = MagicMock(return_value=f"```python\n{repaired_code}\n```")
    return llm


def _mock_memory(context: str = "", count: int = 0) -> MagicMock:
    memory = MagicMock()
    memory.search_similar = MagicMock(return_value=MemorySearchResult(
        cards=[{"content": context}] if count > 0 else [],
        context=context,
        result_count=count,
    ))
    return memory


# ---------------------------------------------------------------------------
# RepairScriptTool memory integration tests
# ---------------------------------------------------------------------------


class RepairToolMemoryInjectionTests(unittest.TestCase):
    """Verify RepairScriptTool searches and injects agent memory."""

    def _make_kwargs(self, **overrides) -> dict:
        defaults = {
            "prompt": "打开百度搜索 Selenium",
            "original_code": "driver.find_element(By.ID, 'kw')",
            "error": "NoSuchElementException: unable to locate element",
            "logs": "",
            "context": "",
        }
        defaults.update(overrides)
        return defaults

    def test_memory_context_injected_into_repair_prompt(self):
        """When memory has results, the context is passed to repair_script."""
        llm = _mock_llm()
        memory = _mock_memory(
            context="# Agent Memory: Baidu kw selector\n## 修复动作\nUse input[name='wd']",
            count=1,
        )
        tool = RepairScriptTool(llm, memory_service=memory)
        result = tool.execute(**self._make_kwargs())

        self.assertTrue(result.success)
        # Verify memory was searched
        memory.search_similar.assert_called_once()
        search_call = memory.search_similar.call_args
        self.assertIn("NoSuchElementException", search_call[1]["query"])
        self.assertEqual(search_call[1]["card_type"], "heal")
        # Verify memory_context was passed to LLM
        repair_call = llm.repair_script.call_args
        self.assertIn("input[name='wd']", repair_call[1]["memory_context"])

    def test_no_memory_service_still_works(self):
        """Without memory_service, repair proceeds normally."""
        llm = _mock_llm()
        tool = RepairScriptTool(llm, memory_service=None)
        result = tool.execute(**self._make_kwargs())

        self.assertTrue(result.success)
        repair_call = llm.repair_script.call_args
        self.assertEqual(repair_call[1]["memory_context"], "")

    def test_empty_memory_results_passes_empty_context(self):
        """When memory finds nothing, memory_context is empty."""
        llm = _mock_llm()
        memory = _mock_memory(context="", count=0)
        tool = RepairScriptTool(llm, memory_service=memory)
        result = tool.execute(**self._make_kwargs())

        self.assertTrue(result.success)
        memory.search_similar.assert_called_once()
        repair_call = llm.repair_script.call_args
        self.assertEqual(repair_call[1]["memory_context"], "")

    def test_memory_exception_does_not_break_repair(self):
        """If memory search raises, repair proceeds with empty context."""
        llm = _mock_llm()
        memory = MagicMock()
        memory.search_similar.side_effect = RuntimeError("ChromaDB down")
        tool = RepairScriptTool(llm, memory_service=memory)
        result = tool.execute(**self._make_kwargs())

        self.assertTrue(result.success)
        repair_call = llm.repair_script.call_args
        self.assertEqual(repair_call[1]["memory_context"], "")

    def test_search_query_contains_error_and_prompt(self):
        """Memory search query includes both error and scenario info."""
        llm = _mock_llm()
        memory = _mock_memory(count=0)
        tool = RepairScriptTool(llm, memory_service=memory)
        tool.execute(**self._make_kwargs(
            error="TimeoutException at line 15",
            prompt="login to vue-admin",
        ))

        query = memory.search_similar.call_args[1]["query"]
        self.assertIn("TimeoutException", query)
        self.assertIn("login to vue-admin", query)


# ---------------------------------------------------------------------------
# LLMService.repair_script memory_context integration
# ---------------------------------------------------------------------------


class LLMServiceMemoryBlockTests(unittest.TestCase):
    """Verify memory_context is rendered into the repair prompt."""

    def test_memory_block_in_prompt_when_provided(self):
        """When memory_context is non-empty, it appears in the repair prompt."""
        from app.services.llm_service import LLMService

        llm = LLMService.__new__(LLMService)
        # Capture the messages sent to _complete
        captured = {}
        def fake_complete(*, messages, model_config=None):
            captured["messages"] = messages
            return "print('fixed')"
        llm._complete = fake_complete

        llm.repair_script(
            prompt="test",
            original_code="code",
            error="err",
            logs="",
            context="",
            memory_context="## 修复动作\nUse #loginForm instead of #login",
        )

        user_msg = captured["messages"][1]["content"]
        self.assertIn("[HISTORICAL EXPERIENCE]", user_msg)
        self.assertIn("Use #loginForm instead of #login", user_msg)

    def test_no_memory_block_when_empty(self):
        """When memory_context is empty, the block is omitted."""
        from app.services.llm_service import LLMService

        llm = LLMService.__new__(LLMService)
        captured = {}
        def fake_complete(*, messages, model_config=None):
            captured["messages"] = messages
            return "print('fixed')"
        llm._complete = fake_complete

        llm.repair_script(
            prompt="test",
            original_code="code",
            error="err",
            logs="",
            context="",
            memory_context="",
        )

        user_msg = captured["messages"][1]["content"]
        self.assertNotIn("Historical repair experience", user_msg)


# ---------------------------------------------------------------------------
# Site profile injection into repair flow
# ---------------------------------------------------------------------------


class RepairToolSiteProfileTests(unittest.TestCase):
    """Verify RepairScriptTool injects site profile block into repair."""

    def setUp(self) -> None:
        self._tmp_dir = Path(tempfile.mkdtemp())
        self.sps = SiteProfileService(storage_dir=self._tmp_dir)
        self.sps.save_profile(
            SiteProfile(
                site_url="example.com",
                execution_count=5,
                success_count=3,
                last_updated="2025-06-01T00:00:00+00:00",
                known_selectors={"auto_extracted": ["#submit-btn"]},
            )
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _make_kwargs(self, **overrides) -> dict:
        defaults = {
            "prompt": "打开 https://example.com 并验证提交",
            "original_code": "driver.find_element(By.ID, 'submit-btn').click()",
            "error": "NoSuchElementException: unable to locate element",
            "logs": "",
            "context": "",
        }
        defaults.update(overrides)
        return defaults

    def test_site_profile_block_passed_to_repair_script(self):
        """When site_profile_service has a matching profile, the block is
        passed as site_profile_block to repair_script."""
        llm = _mock_llm()
        tool = RepairScriptTool(llm, site_profile_service=self.sps)
        result = tool.execute(**self._make_kwargs())

        self.assertTrue(result.success)
        repair_call = llm.repair_script.call_args
        block = repair_call[1]["site_profile_block"]
        self.assertIn("example.com", block)
        self.assertIn("#submit-btn", block)

    def test_no_site_profile_service_passes_empty_block(self):
        """Without site_profile_service, site_profile_block is empty."""
        llm = _mock_llm()
        tool = RepairScriptTool(llm, site_profile_service=None)
        result = tool.execute(**self._make_kwargs())

        self.assertTrue(result.success)
        repair_call = llm.repair_script.call_args
        self.assertEqual(repair_call[1]["site_profile_block"], "")

    def test_no_url_in_prompt_passes_empty_block(self):
        """When prompt has no URL, site_profile_block is empty."""
        llm = _mock_llm()
        tool = RepairScriptTool(llm, site_profile_service=self.sps)
        result = tool.execute(**self._make_kwargs(prompt="打开登录页面"))

        self.assertTrue(result.success)
        repair_call = llm.repair_script.call_args
        self.assertEqual(repair_call[1]["site_profile_block"], "")


class LLMServiceSiteProfileBlockTests(unittest.TestCase):
    """Verify site_profile_block is rendered into the repair prompt."""

    def _make_llm_and_capture(self):
        from app.services.llm_service import LLMService
        llm = LLMService.__new__(LLMService)
        captured = {}
        def fake_complete(*, messages, model_config=None):
            captured["messages"] = messages
            return "print('fixed')"
        llm._complete = fake_complete
        return llm, captured

    def _default_strategy_block(self) -> str:
        return "Repair strategy context:\n- strategy_before: interaction_first\n- strategy_after: interaction_first"

    def test_site_profile_block_in_repair_prompt(self):
        """When site_profile_block is non-empty, [Site Profile] appears."""
        llm, captured = self._make_llm_and_capture()
        llm.repair_script(
            prompt="test",
            original_code="code",
            error="err",
            logs="",
            context="",
            site_profile_block="Site: example.com\nExecutions: 5",
        )
        user_msg = captured["messages"][1]["content"]
        self.assertIn("[SITE PROFILE]", user_msg)
        self.assertIn("Site: example.com", user_msg)

    def test_no_site_profile_block_when_empty(self):
        """When site_profile_block is empty, no [Site Profile] section."""
        llm, captured = self._make_llm_and_capture()
        llm.repair_script(
            prompt="test",
            original_code="code",
            error="err",
            logs="",
            context="",
            site_profile_block="",
        )
        user_msg = captured["messages"][1]["content"]
        self.assertNotIn("[Site Profile]", user_msg)


if __name__ == "__main__":
    unittest.main()
