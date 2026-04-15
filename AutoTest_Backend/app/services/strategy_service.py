from __future__ import annotations

import re
from dataclasses import dataclass


INTERACTION_FIRST = "interaction_first"
RESULT_FIRST = "result_first"

SITE_PROFILE_BAIDU_SEARCH = "baidu_search"

FALLBACK_REASON_BAIDU_HOMEPAGE_TIMEOUT = "baidu_homepage_search_anchor_timeout"
FALLBACK_REASON_BAIDU_HOMEPAGE_FAILURE = "baidu_homepage_search_anchor_failure"

SEARCH_TERMS = ("搜索", "搜寻", "检索", "查询", "search")
BAIDU_TERMS = ("百度", "baidu")
RESULT_ONLY_TERMS = (
    "只验证结果",
    "只验证搜索结果",
    "直接打开结果页",
    "直接访问结果页",
    "直接进入结果页",
    "skip homepage",
    "skip the homepage",
    "direct results page",
    "result only",
    "result-only",
)
HOMEPAGE_REQUIRED_TERMS = (
    "从首页开始",
    "在首页搜索框输入",
    "百度首页搜索框",
    "首页搜索框",
    "点击搜索按钮",
    "模拟用户输入",
    "from homepage",
    "homepage search box",
    "home page search box",
    "type in the homepage search box",
    "click the search button",
    "simulate user typing",
)
HOMEPAGE_SEARCH_MARKERS = (
    "https://www.baidu.com",
    "http://www.baidu.com",
    "driver.get('https://www.baidu.com')",
    'driver.get("https://www.baidu.com")',
    "by.id('kw')",
    'by.id("kw")',
    "input[name='wd']",
    'input[name="wd"]',
    "#kw",
    " kw",
)
TIMEOUT_MARKERS = ("timeout", "timeoutexception")
MISSING_MARKERS = ("no such element", "unable to locate", "not found", "找不到")


@dataclass(slots=True)
class StrategyContext:
    requested_strategy: str = INTERACTION_FIRST
    effective_strategy: str = INTERACTION_FIRST
    fallback_allowed: bool = False
    fallback_reason: str | None = None
    site_profile: str | None = None


@dataclass(slots=True)
class RepairStrategyDecision:
    requested_strategy: str
    strategy_before: str
    strategy_after: str
    fallback_allowed: bool
    fallback_reason: str | None = None
    site_profile: str | None = None

    @property
    def downgraded(self) -> bool:
        return self.strategy_before != self.strategy_after


class StrategyService:
    def analyze_generation(self, prompt: str) -> StrategyContext:
        normalized_prompt = self._normalize(prompt)
        site_profile = (
            SITE_PROFILE_BAIDU_SEARCH if self._is_baidu_search_prompt(normalized_prompt) else None
        )
        requires_homepage = self.requires_homepage_search_flow(normalized_prompt)
        wants_result_only = self._contains_any(normalized_prompt, RESULT_ONLY_TERMS)

        effective_strategy = INTERACTION_FIRST
        if site_profile == SITE_PROFILE_BAIDU_SEARCH and wants_result_only and not requires_homepage:
            effective_strategy = RESULT_FIRST

        return StrategyContext(
            requested_strategy=INTERACTION_FIRST,
            effective_strategy=effective_strategy,
            fallback_allowed=site_profile == SITE_PROFILE_BAIDU_SEARCH and not requires_homepage,
            site_profile=site_profile,
        )

    def analyze_repair(
        self,
        *,
        prompt: str,
        error: str | None,
        original_code: str,
        requested_strategy: str = INTERACTION_FIRST,
        effective_strategy: str = INTERACTION_FIRST,
        site_profile: str | None = None,
    ) -> RepairStrategyDecision:
        generation_context = self.analyze_generation(prompt)
        resolved_site_profile = site_profile or generation_context.site_profile
        strategy_before = effective_strategy or generation_context.effective_strategy
        strategy_after = strategy_before
        fallback_reason = None
        fallback_allowed = generation_context.fallback_allowed

        if (
            resolved_site_profile == SITE_PROFILE_BAIDU_SEARCH
            and strategy_before == INTERACTION_FIRST
            and fallback_allowed
        ):
            fallback_reason = self._baidu_fallback_reason(prompt, error, original_code)
            if fallback_reason:
                strategy_after = RESULT_FIRST

        return RepairStrategyDecision(
            requested_strategy=requested_strategy or generation_context.requested_strategy,
            strategy_before=strategy_before,
            strategy_after=strategy_after,
            fallback_allowed=fallback_allowed,
            fallback_reason=fallback_reason,
            site_profile=resolved_site_profile,
        )

    def requires_homepage_search_flow(self, prompt_or_normalized_prompt: str) -> bool:
        normalized_prompt = self._normalize(prompt_or_normalized_prompt)
        return self._contains_any(normalized_prompt, HOMEPAGE_REQUIRED_TERMS)

    def is_baidu_search_prompt(self, prompt_or_normalized_prompt: str) -> bool:
        normalized_prompt = self._normalize(prompt_or_normalized_prompt)
        return self._is_baidu_search_prompt(normalized_prompt)

    def looks_like_baidu_homepage_code(self, code: str) -> bool:
        lowered = code.lower()
        has_homepage_url = (
            ("https://www.baidu.com" in lowered or "http://www.baidu.com" in lowered)
            and "baidu.com/s?wd=" not in lowered
        )
        has_homepage_input = any(marker in lowered for marker in HOMEPAGE_SEARCH_MARKERS)
        return has_homepage_url or has_homepage_input

    def build_strategy_block(self, context: StrategyContext) -> str:
        lines = [
            "Strategy context:",
            f"- requested_strategy: {context.requested_strategy}",
            f"- effective_strategy: {context.effective_strategy}",
            f"- fallback_allowed: {'yes' if context.fallback_allowed else 'no'}",
            f"- site_profile: {context.site_profile or 'generic'}",
            "- interaction_first means the first generated script must preserve the requested UI interaction flow instead of skipping directly to a result URL.",
            "- result_first means a direct result URL is allowed only because the user explicitly asked for result-only verification or a repair strategy explicitly permits it.",
        ]
        return "\n".join(lines)

    def build_repair_strategy_block(self, decision: RepairStrategyDecision) -> str:
        lines = [
            "Repair strategy context:",
            f"- requested_strategy: {decision.requested_strategy}",
            f"- strategy_before: {decision.strategy_before}",
            f"- strategy_after: {decision.strategy_after}",
            f"- fallback_allowed: {'yes' if decision.fallback_allowed else 'no'}",
            f"- fallback_reason: {decision.fallback_reason or 'none'}",
            f"- site_profile: {decision.site_profile or 'generic'}",
        ]
        return "\n".join(lines)

    def build_repair_summary(self, decision: RepairStrategyDecision) -> str | None:
        if not decision.downgraded:
            return None
        if decision.fallback_reason == FALLBACK_REASON_BAIDU_HOMEPAGE_TIMEOUT:
            return (
                "Switched from homepage search input flow to direct Baidu results page "
                "after homepage search anchor timeout."
            )
        if decision.fallback_reason == FALLBACK_REASON_BAIDU_HOMEPAGE_FAILURE:
            return (
                "Switched from homepage search input flow to direct Baidu results page "
                "after homepage search anchor failure."
            )
        return (
            f"Switched execution strategy from {decision.strategy_before} to "
            f"{decision.strategy_after}."
        )

    def build_repair_guidance(self, decision: RepairStrategyDecision) -> str:
        if (
            decision.site_profile != SITE_PROFILE_BAIDU_SEARCH
            or not decision.downgraded
            or decision.strategy_after != RESULT_FIRST
        ):
            return ""

        return (
            "This failure matches the Baidu homepage search-input path. "
            "Preserve the business goal, but downgrade the execution strategy from "
            "interaction_first to result_first for this repair only. "
            "Use urllib.parse.quote_plus to encode the keyword, open "
            "https://www.baidu.com/s?wd=<encoded keyword>, wait for body and #content_left, "
            "assert at least one visible result link under #content_left h3 a, and only then "
            "print exactly print('Test Completed'). Do not keep retrying the homepage #kw or "
            "input[name='wd'] path."
        )

    def _baidu_fallback_reason(
        self,
        prompt: str,
        error: str | None,
        original_code: str,
    ) -> str | None:
        normalized_prompt = self._normalize(prompt)
        if not self._is_baidu_search_prompt(normalized_prompt):
            return None
        if self.requires_homepage_search_flow(normalized_prompt):
            return None

        combined = f"{prompt}\n{error or ''}\n{original_code}".lower()
        has_homepage_marker = self.looks_like_baidu_homepage_code(original_code) or any(
            marker in combined for marker in HOMEPAGE_SEARCH_MARKERS
        )
        already_results_page = "baidu.com/s?wd=" in combined
        if not has_homepage_marker or already_results_page:
            return None

        if any(marker in combined for marker in TIMEOUT_MARKERS):
            return FALLBACK_REASON_BAIDU_HOMEPAGE_TIMEOUT
        if any(marker in combined for marker in MISSING_MARKERS):
            return FALLBACK_REASON_BAIDU_HOMEPAGE_FAILURE
        return None

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", "", text).lower()

    def _contains_any(self, text: str, terms: tuple[str, ...]) -> bool:
        return any(term.lower() in text for term in terms)

    def _is_baidu_search_prompt(self, normalized_prompt: str) -> bool:
        return self._contains_any(normalized_prompt, SEARCH_TERMS) and self._contains_any(
            normalized_prompt, BAIDU_TERMS
        )
