from app.core.exceptions import AppError
from app.repositories import TestCaseRepository
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.utils.code_parser import clean_code


class GenerationService:
    def __init__(
        self,
        llm_service: LLMService,
        rag_service: RAGService,
        test_case_repository: TestCaseRepository,
    ) -> None:
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.test_case_repository = test_case_repository

    def generate(self, prompt: str):
        normalized_prompt = prompt.strip()
        if len(normalized_prompt) < 5:
            raise AppError(
                "Prompt is too short. Please describe the scenario in more detail.",
                status_code=422,
                code="prompt_too_short",
            )

        rag_result = self.rag_service.search(normalized_prompt)
        raw_output = self.llm_service.chat(
            self._build_augmented_prompt(normalized_prompt, rag_result.context)
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
        )
        return record, rag_result

    def _build_augmented_prompt(self, prompt: str, context: str) -> str:
        return (
            "Background knowledge:\n"
            f"{context or 'No additional indexed knowledge was retrieved.'}\n\n"
            "User request:\n"
            f"{prompt}\n\n"
            "Output rules:\n"
            "1. Return Python Selenium code only.\n"
            "2. Use explicit waits instead of blind sleeps when possible.\n"
            "3. Before clear(), send_keys(), click(), or submit(), wait for the element to be "
            "visible or clickable, not just present.\n"
            "4. Prefer submitting search forms with ENTER when it is more reliable than clicking "
            "a separate button.\n"
            "5. Add one concrete success assertion tied to the user request before printing "
            "print('Test Completed').\n"
            "6. Do not print 'Test Completed' inside finally. Use finally only for cleanup such "
            "as driver.quit().\n"
            "7. Avoid unsafe imports or local file operations.\n"
        )

    def _build_title(self, prompt: str) -> str:
        compact = " ".join(prompt.split())
        return compact[:60] if len(compact) > 60 else compact
