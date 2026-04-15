import unittest

from . import _bootstrap

from app.services.strategy_service import StrategyService


class StrategyServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = StrategyService()

    def test_generation_defaults_to_interaction_first_for_baidu_search(self) -> None:
        context = self.service.analyze_generation(
            "打开百度，搜索 DeepSeek，等待结果页面出现，然后打印测试完成。"
        )

        self.assertEqual(context.requested_strategy, "interaction_first")
        self.assertEqual(context.effective_strategy, "interaction_first")
        self.assertTrue(context.fallback_allowed)
        self.assertEqual(context.site_profile, "baidu_search")

    def test_explicit_homepage_prompt_disables_fallback(self) -> None:
        context = self.service.analyze_generation(
            "从首页开始，在百度首页搜索框输入 DeepSeek，并点击搜索按钮。"
        )

        self.assertFalse(context.fallback_allowed)
        self.assertEqual(context.effective_strategy, "interaction_first")

    def test_repair_allows_baidu_downgrade_after_homepage_timeout(self) -> None:
        decision = self.service.analyze_repair(
            prompt="打开百度，搜索 DeepSeek，等待结果页面出现，然后打印测试完成。",
            error="TimeoutException: kw timed out",
            original_code="driver.get('https://www.baidu.com')\nsearch = driver.find_element(By.ID, 'kw')",
            requested_strategy="interaction_first",
            effective_strategy="interaction_first",
            site_profile="baidu_search",
        )

        self.assertEqual(decision.strategy_before, "interaction_first")
        self.assertEqual(decision.strategy_after, "result_first")
        self.assertEqual(decision.fallback_reason, "baidu_homepage_search_anchor_timeout")

    def test_repair_respects_explicit_homepage_requirement(self) -> None:
        decision = self.service.analyze_repair(
            prompt="从首页开始，在百度首页搜索框输入 DeepSeek，并点击搜索按钮。",
            error="TimeoutException: kw timed out",
            original_code="driver.get('https://www.baidu.com')\nsearch = driver.find_element(By.ID, 'kw')",
            requested_strategy="interaction_first",
            effective_strategy="interaction_first",
            site_profile="baidu_search",
        )

        self.assertEqual(decision.strategy_before, "interaction_first")
        self.assertEqual(decision.strategy_after, "interaction_first")
        self.assertIsNone(decision.fallback_reason)


if __name__ == "__main__":
    unittest.main()
