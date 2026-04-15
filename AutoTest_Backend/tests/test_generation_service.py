import unittest

from . import _bootstrap

from app.services.generation_service import GenerationService
from app.services.llm_service import SELF_HEAL_PROMPT, SYSTEM_PROMPT
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


if __name__ == "__main__":
    unittest.main()
