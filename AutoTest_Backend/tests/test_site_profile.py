"""Tests for SiteProfile dataclass + SiteProfileService."""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from . import _bootstrap  # noqa: F401

from app.services.site_profile_service import (
    SiteProfile,
    SiteProfileService,
    _extract_selectors_from_text,
)

from tests.runtime_support import get_runtime_root


def _tmp_dir(name: str = "site_profiles") -> Path:
    d = get_runtime_root() / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# SiteProfile dataclass tests
# ---------------------------------------------------------------------------


class TestSiteProfileDataclass(unittest.TestCase):
    """Tests for the SiteProfile dataclass."""

    def test_defaults(self):
        p = SiteProfile(site_url="example.com")
        self.assertEqual(p.site_url, "example.com")
        self.assertEqual(p.known_selectors, {})
        self.assertEqual(p.page_load_patterns, {})
        self.assertEqual(p.common_failure_patterns, [])
        self.assertEqual(p.successful_strategies, [])
        self.assertEqual(p.execution_count, 0)
        self.assertEqual(p.success_count, 0)
        self.assertEqual(p.last_updated, "")

    def test_to_dict(self):
        p = SiteProfile(site_url="a.com", execution_count=3)
        d = p.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["site_url"], "a.com")
        self.assertEqual(d["execution_count"], 3)

    def test_from_dict(self):
        data = {"site_url": "b.com", "success_count": 5, "extra_field": "ignored"}
        p = SiteProfile.from_dict(data)
        self.assertEqual(p.site_url, "b.com")
        self.assertEqual(p.success_count, 5)

    def test_round_trip(self):
        p = SiteProfile(
            site_url="c.com",
            known_selectors={"login": ["#btn"]},
            common_failure_patterns=["timeout"],
            execution_count=7,
            success_count=4,
        )
        p2 = SiteProfile.from_dict(p.to_dict())
        self.assertEqual(p.to_dict(), p2.to_dict())


# ---------------------------------------------------------------------------
# _normalize_url
# ---------------------------------------------------------------------------


class TestNormalizeUrl(unittest.TestCase):

    def test_full_url(self):
        self.assertEqual(SiteProfileService._normalize_url("https://Example.COM/path"), "example.com")

    def test_url_with_port(self):
        self.assertEqual(SiteProfileService._normalize_url("http://localhost:8080/foo"), "localhost:8080")

    def test_bare_domain(self):
        self.assertEqual(SiteProfileService._normalize_url("example.org"), "example.org")

    def test_empty_url(self):
        self.assertEqual(SiteProfileService._normalize_url(""), "")


# ---------------------------------------------------------------------------
# _extract_selectors_from_text
# ---------------------------------------------------------------------------


class TestExtractSelectors(unittest.TestCase):

    def test_id_selector(self):
        self.assertIn("#login-btn", _extract_selectors_from_text("could not find #login-btn"))

    def test_class_selector(self):
        self.assertIn(".search-box", _extract_selectors_from_text("missing .search-box"))

    def test_attr_selector(self):
        self.assertIn("input[name=query]", _extract_selectors_from_text("input[name=query] not found"))

    def test_empty_input(self):
        self.assertEqual(_extract_selectors_from_text(""), [])

    def test_no_selectors(self):
        self.assertEqual(_extract_selectors_from_text("everything works fine"), [])


# ---------------------------------------------------------------------------
# SiteProfileService CRUD
# ---------------------------------------------------------------------------


class TestSiteProfileServiceCRUD(unittest.TestCase):

    def setUp(self):
        self.svc = SiteProfileService(storage_dir=_tmp_dir("sp_crud"))

    def test_get_profile_nonexistent(self):
        self.assertIsNone(self.svc.get_profile("https://never-seen.com"))

    def test_save_and_get(self):
        p = SiteProfile(site_url="save-test.com", execution_count=1)
        self.svc.save_profile(p)
        loaded = self.svc.get_profile("https://save-test.com/page")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.site_url, "save-test.com")
        self.assertEqual(loaded.execution_count, 1)

    def test_save_empty_url_ignored(self):
        p = SiteProfile(site_url="")
        self.svc.save_profile(p)  # should not raise

    def test_corrupted_json_returns_none(self):
        svc = SiteProfileService(storage_dir=_tmp_dir("sp_corrupt"))
        # Write bad JSON
        path = svc._profile_path("bad.com")
        path.write_text("{invalid json", encoding="utf-8")
        self.assertIsNone(svc.get_profile("http://bad.com"))


# ---------------------------------------------------------------------------
# update_from_execution
# ---------------------------------------------------------------------------


class TestUpdateFromExecution(unittest.TestCase):

    def setUp(self):
        self.svc = SiteProfileService(storage_dir=_tmp_dir("sp_update"))

    def test_creates_profile_on_first_call(self):
        p = self.svc.update_from_execution("https://new-site.com/login", status="success")
        self.assertEqual(p.execution_count, 1)
        self.assertEqual(p.success_count, 1)
        self.assertNotEqual(p.last_updated, "")

    def test_increments_execution_count(self):
        self.svc.update_from_execution("https://counter.com", status="failure", error="e1")
        p = self.svc.update_from_execution("https://counter.com", status="success")
        self.assertEqual(p.execution_count, 2)
        self.assertEqual(p.success_count, 1)

    def test_failure_appends_pattern(self):
        p = self.svc.update_from_execution(
            "https://fail-pat.com", status="failure",
            error="element_not_found on .search-btn",
            diagnosis="selector missing",
        )
        self.assertTrue(len(p.common_failure_patterns) >= 1)
        self.assertIn("element_not_found", p.common_failure_patterns[0])

    def test_success_appends_strategy(self):
        p = self.svc.update_from_execution(
            "https://strat.com", status="success", strategy="wait_and_retry",
        )
        self.assertIn("wait_and_retry", p.successful_strategies)

    def test_duplicate_strategy_not_appended(self):
        self.svc.update_from_execution("https://dup.com", status="success", strategy="s1")
        p = self.svc.update_from_execution("https://dup.com", status="success", strategy="s1")
        self.assertEqual(p.successful_strategies.count("s1"), 1)

    def test_selector_extraction_from_error(self):
        p = self.svc.update_from_execution(
            "https://sel.com", status="failure",
            error="cannot find #login-btn", logs=".result-list missing",
        )
        auto = p.known_selectors.get("auto_extracted", [])
        self.assertIn("#login-btn", auto)
        self.assertIn(".result-list", auto)

    def test_duplicate_failure_pattern_not_appended(self):
        self.svc.update_from_execution(
            "https://dedup.com", status="failure", error="timeout", diagnosis="slow",
        )
        p = self.svc.update_from_execution(
            "https://dedup.com", status="failure", error="timeout", diagnosis="slow",
        )
        # Same snippet should appear only once
        snippet = SiteProfileService._build_failure_snippet("timeout", "slow")
        self.assertEqual(p.common_failure_patterns.count(snippet), 1)


# ---------------------------------------------------------------------------
# get_profile_prompt_block
# ---------------------------------------------------------------------------


class TestGetProfilePromptBlock(unittest.TestCase):

    def setUp(self):
        self.svc = SiteProfileService(storage_dir=_tmp_dir("sp_prompt"))

    def test_empty_when_no_profile(self):
        self.assertEqual(self.svc.get_profile_prompt_block("https://no.com"), "")

    def test_contains_site_url(self):
        self.svc.update_from_execution("https://prompt-test.com", status="success")
        block = self.svc.get_profile_prompt_block("https://prompt-test.com")
        self.assertIn("prompt-test.com", block)

    def test_contains_execution_stats(self):
        self.svc.update_from_execution("https://stats.com", status="success")
        block = self.svc.get_profile_prompt_block("https://stats.com")
        self.assertIn("Executions: 1", block)
        self.assertIn("Successes: 1", block)

    def test_max_chars_truncation(self):
        self.svc.update_from_execution(
            "https://trunc.com", status="failure",
            error="x" * 200, diagnosis="y" * 200,
        )
        block = self.svc.get_profile_prompt_block("https://trunc.com", max_chars=100)
        self.assertLessEqual(len(block), 100)
        self.assertTrue(block.endswith("..."))

    def test_includes_failure_patterns(self):
        self.svc.update_from_execution(
            "https://fp.com", status="failure", error="element_not_found on .btn",
        )
        block = self.svc.get_profile_prompt_block("https://fp.com")
        self.assertIn("Common failures", block)

    def test_includes_successful_strategies(self):
        self.svc.update_from_execution("https://ss.com", status="success", strategy="retry_v2")
        block = self.svc.get_profile_prompt_block("https://ss.com")
        self.assertIn("retry_v2", block)


# ---------------------------------------------------------------------------
# 3.5b Integration: ExecutionService → SiteProfile update
# ---------------------------------------------------------------------------


class TestExecutionServiceSiteProfileIntegration(unittest.TestCase):
    """Verify that ExecutionService._update_site_profile calls SiteProfileService."""

    def test_extract_target_url_from_prompt(self):
        """URL in prompt takes priority over code."""
        from app.services.execution_service import ExecutionService

        url = ExecutionService._extract_target_url(
            prompt="请打开 https://www.baidu.com 搜索 AI",
            code='driver.get("https://fallback.com")',
        )
        self.assertEqual(url, "https://www.baidu.com")

    def test_extract_target_url_from_code(self):
        """Falls back to driver.get(...) when prompt has no URL."""
        from app.services.execution_service import ExecutionService

        url = ExecutionService._extract_target_url(
            prompt="在百度搜索 AI",
            code='driver.get("https://www.baidu.com")',
        )
        self.assertEqual(url, "https://www.baidu.com")

    def test_extract_target_url_none(self):
        """Returns empty string when no URL found anywhere."""
        from app.services.execution_service import ExecutionService

        url = ExecutionService._extract_target_url(
            prompt="无 URL 的提示",
            code="print('hello')",
        )
        self.assertEqual(url, "")

    def test_update_site_profile_called_after_execution(self):
        """Simulates _update_site_profile writing to SiteProfileService."""
        from unittest.mock import MagicMock

        from app.services.execution_service import ExecutionService

        # Create a real SiteProfileService with a temp dir
        svc = SiteProfileService(storage_dir=_tmp_dir("sp_exec_integration"))

        # Build a minimal mock ExecutionService with just the fields we need
        exec_svc = object.__new__(ExecutionService)
        exec_svc.site_profile_service = svc

        # Mock repos
        mock_exec_repo = MagicMock()
        mock_tc_repo = MagicMock()
        exec_svc.execution_repository = mock_exec_repo
        exec_svc.test_case_repository = mock_tc_repo

        # Simulate a completed execution record
        mock_record = MagicMock()
        mock_record.status = "completed"
        mock_record.executed_code = 'driver.get("https://integration-test.com/login")'
        mock_record.error = ""
        mock_record.logs = ""
        mock_record.effective_strategy = "interaction_first"
        mock_record.test_case_id = "tc-1"
        mock_exec_repo.get.return_value = mock_record

        mock_tc = MagicMock()
        mock_tc.prompt = "登录 https://integration-test.com"
        mock_tc_repo.get.return_value = mock_tc

        # Invoke _update_site_profile
        exec_svc._update_site_profile("exec-1")

        # Verify profile was created
        profile = svc.get_profile("https://integration-test.com")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.execution_count, 1)
        self.assertEqual(profile.success_count, 1)

    def test_update_site_profile_records_failure(self):
        """Failure status is recorded correctly in the site profile."""
        from unittest.mock import MagicMock

        from app.services.execution_service import ExecutionService

        svc = SiteProfileService(storage_dir=_tmp_dir("sp_exec_failure"))

        exec_svc = object.__new__(ExecutionService)
        exec_svc.site_profile_service = svc
        exec_svc.execution_repository = MagicMock()
        exec_svc.test_case_repository = MagicMock()

        mock_record = MagicMock()
        mock_record.status = "failed"
        mock_record.executed_code = 'driver.get("https://fail-site.com/page")'
        mock_record.error = "element not found #submit-btn"
        mock_record.logs = ""
        mock_record.effective_strategy = "interaction_first"
        mock_record.test_case_id = "tc-2"
        exec_svc.execution_repository.get.return_value = mock_record

        mock_tc = MagicMock()
        mock_tc.prompt = "提交表单"
        exec_svc.test_case_repository.get.return_value = mock_tc

        exec_svc._update_site_profile("exec-2")

        profile = svc.get_profile("https://fail-site.com")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.execution_count, 1)
        self.assertEqual(profile.success_count, 0)
        self.assertTrue(len(profile.common_failure_patterns) >= 1)


if __name__ == "__main__":
    unittest.main()
