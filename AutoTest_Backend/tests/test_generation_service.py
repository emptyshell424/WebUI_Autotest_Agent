import shutil
import tempfile
import unittest
from pathlib import Path

from . import _bootstrap

from app.services.generation_service import GenerationService
from app.services.llm_service import SELF_HEAL_PROMPT, SYSTEM_PROMPT
from app.services.site_profile_service import SiteProfile, SiteProfileService
from app.services.strategy_service import StrategyService


class GenerationPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy_service = StrategyService()
        self.service = GenerationService(
            llm_service=object(),
            rag_service=object(),
            test_case_repository=object(),
            strategy_service=self.strategy_service,
        )

    def test_augmented_prompt_contains_bilingual_and_safety_rules(self) -> None:
        strategy = self.strategy_service.analyze_generation(
            "打开登录页面，输入用户名 admin 和密码 111111，然后验证进入首页。"
        )
        prompt = self.service._build_augmented_prompt(
            "打开登录页面，输入用户名 admin 和密码 111111，然后验证进入首页。",
            "登录后应断言 name: admin。",
            strategy,
        )

        self.assertIn("Background knowledge", prompt)
        self.assertIn("Do not import sys, os, subprocess, pathlib", prompt)
        self.assertIn("Do not add ChromeOptions", prompt)
        self.assertIn("The user request may be written in Chinese or English", prompt)
        self.assertIn("Interpreted task hints", prompt)
        self.assertIn("requested_strategy: interaction_first", prompt)

    def test_baidu_search_prompt_defaults_to_homepage_interaction_first(self) -> None:
        strategy = self.strategy_service.analyze_generation(
            "打开百度，搜索 DeepSeek，等待结果页面出现，然后打印测试完成。"
        )
        prompt = self.service._build_augmented_prompt(
            "打开百度，搜索 DeepSeek，等待结果页面出现，然后打印测试完成。",
            "百度搜索应优先保持首页交互语义。",
            strategy,
        )

        self.assertEqual(strategy.requested_strategy, "interaction_first")
        self.assertEqual(strategy.effective_strategy, "interaction_first")
        self.assertTrue(strategy.fallback_allowed)
        self.assertIn("defaults to interaction_first", prompt)
        self.assertIn("Start at https://www.baidu.com", prompt)
        self.assertNotIn("prefer opening the results page directly", prompt)

    def test_explicit_homepage_search_prompt_disables_fallback(self) -> None:
        strategy = self.strategy_service.analyze_generation(
            "从首页开始，在百度首页搜索框输入 DeepSeek，并点击搜索按钮。"
        )
        prompt = self.service._build_augmented_prompt(
            "从首页开始，在百度首页搜索框输入 DeepSeek，并点击搜索按钮。",
            "用户明确要求首页交互。",
            strategy,
        )

        self.assertFalse(strategy.fallback_allowed)
        self.assertIn("defaults to interaction_first", prompt)
        self.assertNotIn("reserved for self-heal", prompt)

    def test_system_prompts_emphasize_strategy_context(self) -> None:
        self.assertIn("Chinese", SYSTEM_PROMPT)
        self.assertIn("Do not import sys, os, pathlib, subprocess", SYSTEM_PROMPT)
        self.assertIn("Obey the supplied strategy context", SYSTEM_PROMPT)
        self.assertIn("Keep the user intent unchanged", SELF_HEAL_PROMPT)
        self.assertIn("repair strategy", SELF_HEAL_PROMPT)


class SiteProfileInjectionTests(unittest.TestCase):
    """Tests for site-profile injection in _build_augmented_prompt / _get_site_profile_block."""

    def setUp(self) -> None:
        self.strategy_service = StrategyService()
        self._tmp_dir = Path(tempfile.mkdtemp())
        self.sps = SiteProfileService(storage_dir=self._tmp_dir)
        self.service = GenerationService(
            llm_service=object(),
            rag_service=object(),
            test_case_repository=object(),
            strategy_service=self.strategy_service,
            site_profile_service=self.sps,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_site_profile_block_injected_into_prompt(self) -> None:
        """When a non-empty site_profile_block is supplied, it must appear
        between the strategy block and the User request block."""
        strategy = self.strategy_service.analyze_generation(
            "打开 https://example.com 并验证标题"
        )
        prompt = self.service._build_augmented_prompt(
            "打开 https://example.com 并验证标题",
            "some context",
            strategy,
            site_profile_block="Site: example.com\nExecutions: 5",
        )
        self.assertIn("[Site Profile]", prompt)
        self.assertIn("Site: example.com", prompt)
        # Profile section should appear before "User request:"
        profile_pos = prompt.index("[Site Profile]")
        user_pos = prompt.index("User request:")
        self.assertLess(profile_pos, user_pos)

    def test_no_profile_block_when_empty(self) -> None:
        """When site_profile_block is None or empty, no [Site Profile] section
        should appear in the prompt."""
        strategy = self.strategy_service.analyze_generation("打开登录页面")
        for value in (None, ""):
            prompt = self.service._build_augmented_prompt(
                "打开登录页面",
                "ctx",
                strategy,
                site_profile_block=value,
            )
            self.assertNotIn("[Site Profile]", prompt)

    def test_get_site_profile_block_returns_profile_for_known_url(self) -> None:
        """_get_site_profile_block should locate the URL in the prompt,
        look up the profile, and return its prompt block."""
        # Seed a profile for example.com.
        self.sps.save_profile(
            SiteProfile(
                site_url="example.com",
                execution_count=3,
                success_count=2,
                last_updated="2025-01-01T00:00:00+00:00",
                known_selectors={"auto_extracted": ["#login-btn"]},
            )
        )
        block = self.service._get_site_profile_block(
            "打开 https://example.com/login 并登录"
        )
        self.assertIn("example.com", block)
        self.assertIn("#login-btn", block)

    def test_get_site_profile_block_empty_when_no_url(self) -> None:
        """When the prompt contains no URL, return empty string."""
        block = self.service._get_site_profile_block("打开百度搜索")
        self.assertEqual(block, "")

    def test_get_site_profile_block_empty_when_no_service(self) -> None:
        """When site_profile_service is None, return empty string."""
        service_no_sps = GenerationService(
            llm_service=object(),
            rag_service=object(),
            test_case_repository=object(),
            strategy_service=self.strategy_service,
            site_profile_service=None,
        )
        block = service_no_sps._get_site_profile_block(
            "打开 https://example.com 并验证"
        )
        self.assertEqual(block, "")


if __name__ == "__main__":
    unittest.main()
