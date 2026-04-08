from openai import OpenAI

from app.core.config import Settings
from app.core.exceptions import AppError


SYSTEM_PROMPT = (
    "You are a senior Python Selenium engineer. "
    "Return only executable Python code. Prefer robust browser automation over concise code. "
    "Use explicit waits with visibility_of_element_located or element_to_be_clickable before "
    "clear(), send_keys(), click(), or submit(). Prefer resilient selectors. Submit searches "
    "with ENTER when that is more reliable than clicking a button. Print('Test Completed') "
    "only after the target assertion succeeds, not inside finally."
)

SELF_HEAL_PROMPT = (
    "You are repairing a failed Python Selenium script. "
    "Return only executable Python Selenium code. "
    "Keep the user intent unchanged, use resilient selectors and explicit waits, "
    "and avoid unsafe imports or local file operations."
)


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: OpenAI | None = None

    def chat(self, prompt: str) -> str:
        return self._complete(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
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
    ) -> str:
        repair_prompt = (
            "Original user request:\n"
            f"{prompt}\n\n"
            "Retrieved knowledge:\n"
            f"{context or 'No additional indexed knowledge was retrieved.'}\n\n"
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
            "5. Return Python code only.\n"
        )
        return self._complete(
            messages=[
                {"role": "system", "content": SELF_HEAL_PROMPT},
                {"role": "user", "content": repair_prompt},
            ]
        )

    def _complete(self, *, messages: list[dict[str, str]]) -> str:
        client = self._get_client()
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
            raise AppError(
                "LLM request failed.",
                status_code=502,
                code="llm_request_failed",
                details={"reason": str(exc)},
            ) from exc

        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise AppError(
                "LLM returned empty content.",
                status_code=502,
                code="llm_empty_response",
            )
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
