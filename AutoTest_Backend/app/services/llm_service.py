import logging
import re

from openai import OpenAI

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.failure_diagnostic_service import FailureDiagnosis
from app.services.model_router import ModelConfig


BASE_SYSTEM_PROMPT = (
    "You are a senior Python Selenium engineer. "
    "The user request may be written in English or Chinese. "
    "Return only executable Python code. Prefer robust browser automation over concise code. "
    "Use explicit waits with visibility_of_element_located or element_to_be_clickable before "
    "clear(), send_keys(), click(), or submit(). Prefer resilient selectors "
    "(id > name > placeholder > CSS > XPath). Never use jQuery-only syntax in CSS selectors "
    "(e.g. :contains() is invalid in standard CSS). "
    "Submit searches with ENTER when that is more reliable than clicking a button. "
    "Print('Test Completed') only after the target assertion succeeds, not inside finally. "
    "Keep imports minimal and only use Selenium-related modules required for the task. "
    "Do not import sys, os, pathlib, subprocess, argparse, or unrelated helpers. "
    "Do not add ChromeOptions, headless flags, sandbox flags, disable-gpu flags, "
    "or fixed window-size arguments unless the user explicitly asks for them. "
    "Obey the supplied strategy context. "
    "If the strategy says interaction_first, preserve the original page interaction flow. "
    "If the strategy says result_first, a direct results URL is allowed."
)

SELF_HEAL_SYSTEM_PROMPT = (
    "You are repairing a failed Python Selenium script. "
    "The original request may be written in English or Chinese. "
    "Return only executable Python Selenium code. "
    "The prompt includes a [WHAT WENT WRONG] section with the exact failure analysis "
    "and a [SUGGESTED ALTERNATIVES] section with candidate selectors — use these "
    "as your primary guidance for the fix. "
    "Keep the user intent unchanged. Use resilient selectors (id > name > placeholder > "
    "CSS > XPath). Never use jQuery-only syntax like :contains() in CSS selectors. "
    "Use explicit waits with visibility_of_element_located or element_to_be_clickable. "
    "Keep imports minimal and avoid unsafe imports. Do not add sys, os, pathlib, "
    "subprocess, or browser bootstrap flags unless the failure clearly requires them. "
    "Obey the supplied repair strategy context, including whether a downgrade from "
    "interaction_first to result_first is allowed. "
    "Preserve the parts of the script that ran successfully — only fix what failed."
)

# Backward-compatible exports used by tests.
SYSTEM_PROMPT = BASE_SYSTEM_PROMPT
SELF_HEAL_PROMPT = SELF_HEAL_SYSTEM_PROMPT

logger = logging.getLogger("autotest.llm")

# ---------------------------------------------------------------------------
# Traceback parsing — extract failure context from stderr
# ---------------------------------------------------------------------------

_EXCEPTION_RE = re.compile(
    r"(selenium\.common\.exceptions\.)?(\w+(?:Exception|Error))",
    re.IGNORECASE,
)
_FAILED_SELECTOR_RE = re.compile(
    r"""By\.(\w+)\s*,\s*(["'])(.*?)\2""",
    re.IGNORECASE | re.DOTALL,
)
_LINE_RE = re.compile(
    r"""File\s+".*?",\s*line\s+(\d+)""",
    re.IGNORECASE,
)


def _extract_failure_context(error: str, code: str) -> dict:
    """Parse a Selenium traceback into structured failure context.

    Returns dict with keys: exception_type, failed_selector, failed_line,
    code_context (3 lines around the failure), raw_excerpt (first 500 chars).
    All values are empty strings when unparseable.
    """
    result: dict = {
        "exception_type": "",
        "failed_selector": "",
        "failed_line": "",
        "code_context": "",
        "raw_excerpt": (error or "")[:500],
    }

    if not error:
        return result

    # Exception type
    m = _EXCEPTION_RE.search(error)
    if m:
        result["exception_type"] = m.group(2)

    # Failed selector — take the LAST match (closest to the failure point)
    sel_matches = _FAILED_SELECTOR_RE.findall(error)
    if sel_matches:
        by_method, _quote, selector = sel_matches[-1]
        result["failed_selector"] = f"By.{by_method}, \"{selector}\""

    # Failed line number
    line_matches = _LINE_RE.findall(error)
    if line_matches:
        result["failed_line"] = line_matches[-1]

    # Code context around the failing line
    if result["failed_line"] and code:
        try:
            line_num = int(result["failed_line"])
            code_lines = code.splitlines()
            start = max(0, line_num - 4)
            end = min(len(code_lines), line_num + 3)
            ctx_lines = []
            for i in range(start, end):
                marker = ">>>" if i == line_num - 1 else "   "
                ctx_lines.append(f"{marker} {i + 1}: {code_lines[i]}")
            result["code_context"] = "\n".join(ctx_lines)
        except (ValueError, IndexError):
            pass

    return result


def _build_selector_comparison(
    failed_selector: str,
    suggested_selectors: list[str] | None,
    error_excerpt: str,
) -> str:
    """Build a compact [SUGGESTED ALTERNATIVES] block for the repair prompt."""
    parts: list[str] = []

    if failed_selector:
        parts.append(f"[FAILED SELECTOR]\n  {failed_selector}")

    if suggested_selectors:
        parts.append(
            "[SUGGESTED ALTERNATIVES]\n  "
            + "\n  ".join(suggested_selectors[:6])
        )

    if not parts:
        parts.append(
            f"[FAILURE SIGNAL]\n  {error_excerpt[:300]}"
        )

    return "\n\n".join(parts) if parts else ""


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: OpenAI | None = None

    def chat(self, prompt: str, *, strategy_block: str = "", model_config: ModelConfig | None = None) -> str:
        system_content = f"{BASE_SYSTEM_PROMPT}\n\n{strategy_block}" if strategy_block else BASE_SYSTEM_PROMPT
        return self._complete(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            model_config=model_config,
        )

    def repair_script(
        self,
        *,
        prompt: str,
        original_code: str,
        error: str,
        logs: str,
        context: str,
        failure_diagnosis: FailureDiagnosis | None = None,
        repair_guidance: str = "",
        repair_strategy_block: str = "",
        memory_context: str = "",
        site_profile_block: str = "",
        model_config: ModelConfig | None = None,
    ) -> str:
        # ---- Parse traceback for structured failure context ----
        fc = _extract_failure_context(error or "", original_code)

        # ---- Build what-went-wrong block (top priority) ----
        what_went_wrong: list[str] = []
        if fc["exception_type"]:
            what_went_wrong.append(f"Exception: {fc['exception_type']}")
        if fc["failed_selector"]:
            what_went_wrong.append(f"Failed selector: {fc['failed_selector']}")
        if failure_diagnosis is not None:
            if failure_diagnosis.suspected_root_cause:
                what_went_wrong.append(f"Root cause: {failure_diagnosis.suspected_root_cause}")
            if failure_diagnosis.repair_hint:
                what_went_wrong.append(f"Repair hint: {failure_diagnosis.repair_hint}")
        if fc["code_context"]:
            what_went_wrong.append(f"Failing code:\n{fc['code_context']}")

        # ---- Build selector comparison block ----
        suggested = failure_diagnosis.suggested_selectors if failure_diagnosis is not None else None
        selector_comp = _build_selector_comparison(
            failed_selector=fc["failed_selector"],
            suggested_selectors=suggested,
            error_excerpt=fc["raw_excerpt"],
        )

        # ---- Assemble repair prompt (signal first, noise last) ----
        parts: list[str] = []

        # 1. Repair task
        parts.append(f"[REPAIR TASK]\nOriginal intent: {prompt}")

        # 2. What went wrong
        if what_went_wrong:
            parts.append("[WHAT WENT WRONG]\n" + "\n".join(what_went_wrong))

        # 3. Suggested alternatives
        if selector_comp:
            parts.append(selector_comp)

        # 4. Historical experience (truncated)
        if memory_context:
            parts.append(
                "[HISTORICAL EXPERIENCE]\n"
                f"{memory_context[:1200]}"
            )

        # 5. Repair strategy context
        if repair_strategy_block:
            parts.append(repair_strategy_block)
        if repair_guidance:
            parts.append(f"[REPAIR GUIDANCE]\n{repair_guidance}")

        # 6. Site profile
        if site_profile_block:
            parts.append(f"[SITE PROFILE]\n{site_profile_block}")

        # 7. Failed script
        parts.append(f"[FAILED SCRIPT]\n```python\n{original_code}\n```")

        # 8. Knowledge context
        parts.append(
            "[RETRIEVED KNOWLEDGE]\n"
            f"{context or 'No additional indexed knowledge was retrieved.'}"
        )

        # 9. Repair rules (compact)
        parts.append(
            "[REPAIR RULES]\n"
            "1. Keep the same business intent.\n"
            "2. Fix the root cause — use the [SUGGESTED ALTERNATIVES] above if this is a selector failure.\n"
            "3. Preserve parts of the script that ran successfully; only modify what failed.\n"
            "4. Use resilient selectors (id > name > placeholder > CSS). Never use :contains() in CSS.\n"
            "5. Keep one concrete assertion before print('Test Completed').\n"
            "6. Keep imports minimal. Do not add sys, os, pathlib, subprocess, or ChromeOptions flags.\n"
            "7. If strategy_after=interaction_first, repair the interaction in place.\n"
            "8. If strategy_after=result_first, a direct results URL via urllib.parse.quote_plus is allowed.\n"
            "9. Return Python code only."
        )

        # 10. Raw logs (truncated, lowest priority — for reference only)
        stdout_excerpt = (logs or "(empty)")[:800]
        stderr_excerpt = (error or "(empty)")[:800]
        parts.append(
            "[RAW LOGS — the analysis above is authoritative]\n"
            f"stderr: {stderr_excerpt}\n"
            f"stdout: {stdout_excerpt}"
        )

        repair_prompt = "\n\n".join(parts)

        return self._complete(
            messages=[
                {"role": "system", "content": SELF_HEAL_SYSTEM_PROMPT},
                {"role": "user", "content": repair_prompt},
            ],
            model_config=model_config,
        )

    def _complete(self, *, messages: list[dict[str, str]], model_config: ModelConfig | None = None) -> str:
        model_name = model_config.model_name if model_config else self.settings.MODEL_NAME
        temperature = model_config.temperature if model_config else 0.1
        client = self._get_client(base_url=model_config.base_url if model_config else None)
        logger.info("LLM request: model=%s, messages=%d", model_name, len(messages))
        kwargs: dict = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if model_config and model_config.max_tokens is not None:
            kwargs["max_tokens"] = model_config.max_tokens
        try:
            response = client.chat.completions.create(**kwargs)
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

    def _get_client(self, base_url: str | None = None) -> OpenAI:
        if not self.settings.DEEPSEEK_API_KEY:
            raise AppError(
                "LLM API key is not configured.",
                status_code=503,
                code="llm_not_configured",
            )
        # When a custom base_url is provided, create a one-off client
        if base_url and base_url != self.settings.DEEPSEEK_BASE_URL:
            return OpenAI(
                api_key=self.settings.DEEPSEEK_API_KEY,
                base_url=base_url,
            )
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.DEEPSEEK_API_KEY,
                base_url=self.settings.DEEPSEEK_BASE_URL,
            )
        return self._client

    def agent_chat(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model_config: ModelConfig | None = None,
    ) -> str:
        """Send a system + user message pair for the agent ReAct loop.

        Returns the raw LLM response string (expected to be JSON).
        The caller is responsible for parsing the JSON.
        """
        return self._complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model_config=model_config,
        )

