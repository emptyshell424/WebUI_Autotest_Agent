import logging

from openai import OpenAI

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.strategy_service import RepairStrategyDecision, StrategyContext


BASE_SYSTEM_PROMPT = (
    "You are a senior Python Selenium engineer. "
    "The user request may be written in English or Chinese. "
    "Return only executable Python code. Prefer robust browser automation over concise code. "
    "Use explicit waits with visibility_of_element_located or element_to_be_clickable before "
    "clear(), send_keys(), click(), or submit(). Prefer resilient selectors. Submit searches "
    "with ENTER when that is more reliable than clicking a button. Print('Test Completed') "
    "only after the target assertion succeeds, not inside finally. Keep imports minimal and "
    "only use Selenium-related modules required for the task. Do not import sys, os, pathlib, "
    "subprocess, argparse, or unrelated helpers. Do not add ChromeOptions, headless flags, "
    "sandbox flags, disable-gpu flags, or fixed window-size arguments unless the user explicitly "
    "asks for a special browser runtime configuration. Obey the supplied strategy context. "
    "If the strategy says interaction_first, preserve the original page interaction flow in the "
    "first generated script. If the strategy says result_first, a direct results URL is allowed."
)

SELF_HEAL_SYSTEM_PROMPT = (
    "You are repairing a failed Python Selenium script. "
    "The original request may be written in English or Chinese. "
    "Return only executable Python Selenium code. "
    "Keep the user intent unchanged, use resilient selectors and explicit waits, "
    "keep imports minimal, and avoid unsafe imports or local file operations. Do not add sys, "
    "os, pathlib, subprocess, or unrelated browser bootstrap flags unless the failure clearly "
    "requires them and the request explicitly allows them. Obey the supplied repair strategy "
    "context exactly, including whether a downgrade from interaction_first to result_first is "
    "allowed for this repair attempt."
)

# Backward-compatible exports used by tests.
SYSTEM_PROMPT = BASE_SYSTEM_PROMPT
SELF_HEAL_PROMPT = SELF_HEAL_SYSTEM_PROMPT

logger = logging.getLogger("autotest.llm")


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: OpenAI | None = None

    def chat(self, prompt: str, *, strategy_context: StrategyContext | None = None) -> str:
        strategy_block = (
            f"\n\n{self._render_strategy_context(strategy_context)}"
            if strategy_context is not None
            else ""
        )
        return self._complete(
            messages=[
                {"role": "system", "content": f"{BASE_SYSTEM_PROMPT}{strategy_block}"},
                {"role": "user", "content": prompt},
            ]
        )

    def repair_script(
        self,
        *,
        prompt: str,
        original_code: str,
        error: str,
        logs: str,
        context: str,
        strategy_decision: RepairStrategyDecision,
        repair_guidance: str = "",
    ) -> str:
        repair_guidance_block = (
            "Targeted repair guidance:\n"
            f"{repair_guidance}\n\n"
            if repair_guidance
            else ""
        )
        repair_prompt = (
            "Original user request:\n"
            f"{prompt}\n\n"
            f"{self._render_repair_strategy_context(strategy_decision)}\n\n"
            "Retrieved knowledge:\n"
            f"{context or 'No additional indexed knowledge was retrieved.'}\n\n"
            f"{repair_guidance_block}"
            "Failed script:\n"
            f"{original_code}\n\n"
            "Execution stdout:\n"
            f"{logs or '(empty)'}\n\n"
            "Execution stderr or failure details:\n"
            f"{error or '(empty)'}\n\n"
            "Repair rules:\n"
            "1. Keep the same business intent.\n"
            "2. Fix the likely cause of the failure.\n"
            "3. Use robust waits and selectors.\n"
            "4. Keep one concrete success assertion before printing print('Test Completed').\n"
            "5. Keep imports minimal and avoid sys, os, pathlib, subprocess, or unrelated runtime helpers.\n"
            "6. Do not add ChromeOptions or browser runtime flags unless the user request explicitly needs them.\n"
            "7. If strategy_after stays interaction_first, keep the original interaction path and repair it in place.\n"
            "8. If strategy_after is result_first, the repair may use urllib.parse.quote_plus and a direct results URL only because the repair strategy explicitly allows that downgrade.\n"
            "9. Return Python code only.\n"
        )
        return self._complete(
            messages=[
                {"role": "system", "content": SELF_HEAL_SYSTEM_PROMPT},
                {"role": "user", "content": repair_prompt},
            ]
        )

    def _complete(self, *, messages: list[dict[str, str]]) -> str:
        client = self._get_client()
        logger.info("LLM request: model=%s, messages=%d", self.settings.MODEL_NAME, len(messages))
        try:
            response = client.chat.completions.create(
                model=self.settings.MODEL_NAME,
                messages=messages,
                temperature=0.1,
                stream=False,
            )
        except AppError:
            raise
        except Exception as exc:
            logger.exception("LLM request failed")
            raise AppError(
                "LLM request failed.",
                status_code=502,
                code="llm_request_failed",
                details={"reason": str(exc)},
            ) from exc

        content = (response.choices[0].message.content or "").strip()
        if not content:
            logger.warning("LLM returned empty content")
            raise AppError(
                "LLM returned empty content.",
                status_code=502,
                code="llm_empty_response",
            )
        logger.info("LLM response: %d chars", len(content))
        return content

    def _get_client(self) -> OpenAI:
        if not self.settings.DEEPSEEK_API_KEY:
            raise AppError(
                "LLM API key is not configured.",
                status_code=503,
                code="llm_not_configured",
            )
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.DEEPSEEK_API_KEY,
                base_url=self.settings.DEEPSEEK_BASE_URL,
            )
        return self._client

    def _render_strategy_context(self, strategy_context: StrategyContext) -> str:
        return (
            "Strategy context:\n"
            f"- requested_strategy: {strategy_context.requested_strategy}\n"
            f"- effective_strategy: {strategy_context.effective_strategy}\n"
            f"- fallback_allowed: {'yes' if strategy_context.fallback_allowed else 'no'}\n"
            f"- site_profile: {strategy_context.site_profile or 'generic'}"
        )

    def _render_repair_strategy_context(self, strategy_decision: RepairStrategyDecision) -> str:
        return (
            "Repair strategy context:\n"
            f"- requested_strategy: {strategy_decision.requested_strategy}\n"
            f"- strategy_before: {strategy_decision.strategy_before}\n"
            f"- strategy_after: {strategy_decision.strategy_after}\n"
            f"- fallback_allowed: {'yes' if strategy_decision.fallback_allowed else 'no'}\n"
            f"- fallback_reason: {strategy_decision.fallback_reason or 'none'}\n"
            f"- site_profile: {strategy_decision.site_profile or 'generic'}"
        )
