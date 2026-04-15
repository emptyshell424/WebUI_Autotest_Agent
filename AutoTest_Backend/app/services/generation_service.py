import re

from app.core.exceptions import AppError
from app.repositories import TestCaseRepository
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.strategy_service import (
    RESULT_FIRST,
    SITE_PROFILE_BAIDU_SEARCH,
    StrategyContext,
    StrategyService,
)
from app.utils.code_parser import clean_code

OPEN_TERMS = ("打开", "访问", "进入", "open", "visit")
LOGIN_TERMS = ("登录", "登入", "登陆", "login", "sign in", "log in")
SEARCH_TERMS = ("搜索", "搜寻", "检索", "查询", "search")
RESULT_TERMS = ("结果页", "结果页面", "搜索结果", "结果出现", "results", "result page")
CLICK_TERMS = ("点击", "单击", "click")
INPUT_TERMS = ("输入", "填写", "键入", "input", "type", "send_keys")
ASSERT_TERMS = ("验证", "断言", "校验", "assert", "verify", "check")
PRINT_TERMS = ("打印", "输出", "print", "测试完成", "test completed")


class GenerationService:
    def __init__(
        self,
        llm_service: LLMService,
        rag_service: RAGService,
        test_case_repository: TestCaseRepository,
        strategy_service: StrategyService,
    ) -> None:
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.test_case_repository = test_case_repository
        self.strategy_service = strategy_service

    def generate(self, prompt: str, retrieval_mode: str | None = None):
        normalized_prompt = prompt.strip()
        if len(normalized_prompt) < 5:
            raise AppError(
                "Prompt is too short. Please describe the scenario in more detail.",
                status_code=422,
                code="prompt_too_short",
            )

        strategy_context = self.strategy_service.analyze_generation(normalized_prompt)
        rag_result = self.rag_service.search(
            normalized_prompt,
            retrieval_mode=retrieval_mode,
        )
        raw_output = self.llm_service.chat(
            self._build_augmented_prompt(
                normalized_prompt,
                rag_result.context,
                strategy_context,
            ),
            strategy_context=strategy_context,
        )
        cleaned_code = clean_code(raw_output)
        if not cleaned_code.strip():
            raise AppError(
                "Generated code was empty after cleanup.",
                status_code=502,
                code="empty_generated_code",
            )

        record = self.test_case_repository.create(
            title=self._build_title(normalized_prompt),
            prompt=normalized_prompt,
            generated_code=cleaned_code,
            raw_output=raw_output,
            rag_context=rag_result.context,
            requested_strategy=strategy_context.requested_strategy,
            effective_strategy=strategy_context.effective_strategy,
        )
        return record, rag_result

    def _build_augmented_prompt(
        self,
        prompt: str,
        context: str,
        strategy_context: StrategyContext,
    ) -> str:
        intent_hints = self._build_intent_hints(prompt, strategy_context)
        hint_block = (
            "Interpreted task hints:\n"
            f"{intent_hints}\n\n"
            if intent_hints
            else ""
        )
        return (
            "Background knowledge:\n"
            f"{context or 'No additional indexed knowledge was retrieved.'}\n\n"
            f"{self.strategy_service.build_strategy_block(strategy_context)}\n\n"
            "User request:\n"
            f"{prompt}\n\n"
            f"{hint_block}"
            "Output rules:\n"
            "1. Return Python Selenium code only.\n"
            "2. The user request may be written in Chinese or English. Infer the intended UI flow from the request, interpreted task hints, background knowledge, and strategy context, but still return Python code only.\n"
            "3. Use explicit waits instead of blind sleeps when possible.\n"
            "4. Before clear(), send_keys(), click(), or submit(), wait for the element to be visible or clickable, not just present.\n"
            "5. Prefer submitting search forms with ENTER when it is more reliable than clicking a separate button.\n"
            "6. Add one concrete success assertion tied to the user request before printing print('Test Completed').\n"
            "7. Do not print 'Test Completed' inside finally. Use finally only for cleanup such as driver.quit().\n"
            "8. Keep imports minimal. Only use Selenium modules required for the current task.\n"
            "9. Do not import sys, os, subprocess, pathlib, argparse, or unrelated utility modules.\n"
            "10. Do not add ChromeOptions, headless flags, sandbox flags, disable-gpu flags, or window-size arguments unless the user explicitly requires a special browser runtime configuration.\n"
            "11. Avoid unsafe imports, local file operations, and environment-management code.\n"
            "12. When the effective strategy is interaction_first, preserve the homepage or in-page interaction steps instead of skipping directly to a result URL.\n"
        )

    def _build_intent_hints(self, prompt: str, strategy_context: StrategyContext) -> str:
        compact = self._normalize(prompt)
        hints: list[str] = []

        if self._contains_any(compact, OPEN_TERMS):
            hints.append(
                "- Open the requested page or homepage first, then wait for a stable page anchor before interacting with child elements."
            )
        if self._contains_any(compact, LOGIN_TERMS):
            hints.append(
                "- Treat this as a login flow: wait for username and password inputs, fill them, click the login button, then assert a stable post-login anchor such as dashboard text or a URL change."
            )
        if self._contains_any(compact, SEARCH_TERMS):
            hints.append(
                "- Treat this as a search flow: locate the search input, type the keyword, submit with ENTER or a nearby search button, then assert a stable results container or visible result text."
            )
        if self._contains_any(compact, RESULT_TERMS):
            hints.append(
                "- For result-page verification, wait for a stable results container or result text instead of relying on a transient loading indicator."
            )
        if self._contains_any(compact, CLICK_TERMS):
            hints.append("- Wait for the target control to become clickable before clicking it.")
        if self._contains_any(compact, INPUT_TERMS):
            hints.append("- Wait for input elements to become visible before clear() and send_keys().")
        if self._contains_any(compact, ASSERT_TERMS):
            hints.append(
                "- Add one concrete assertion that matches the requested result instead of only checking that a click happened."
            )
        if self._contains_any(compact, PRINT_TERMS):
            hints.append(
                "- After the real assertion succeeds, print exactly print('Test Completed'). Do not print a translated success string before the assertion."
            )

        if strategy_context.site_profile == SITE_PROFILE_BAIDU_SEARCH:
            if strategy_context.effective_strategy == RESULT_FIRST:
                hints.append(
                    "- The strategy explicitly allows result-first generation for this Baidu search case. Use urllib.parse.quote_plus to build https://www.baidu.com/s?wd=<encoded keyword>."
                )
                hints.append(
                    "- After opening the Baidu results URL, wait for body and #content_left, then assert at least one visible result link in #content_left h3 a before printing print('Test Completed')."
                )
            else:
                hints.append(
                    "- This Baidu search request defaults to interaction_first. Start at https://www.baidu.com, use the homepage search input, submit the keyword, and preserve the real interaction flow in the first generated script."
                )
                if strategy_context.fallback_allowed:
                    hints.append(
                        "- Do not downgrade to the direct Baidu results URL during the first generation. That fallback is reserved for self-heal if homepage search anchors fail later."
                    )

        return "\n".join(hints)

    def _build_title(self, prompt: str) -> str:
        compact = " ".join(prompt.split())
        return compact[:60] if len(compact) > 60 else compact

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", "", text).lower()

    def _contains_any(self, text: str, terms: tuple[str, ...]) -> bool:
        return any(term.lower() in text for term in terms)
