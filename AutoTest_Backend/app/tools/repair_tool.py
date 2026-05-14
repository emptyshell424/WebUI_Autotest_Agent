"""Tool: repair a failed Selenium script via LLM."""

from __future__ import annotations

import re
from typing import Any

from app.services.failure_diagnostic_service import FailureDiagnosticService, FailureDiagnosis
from app.services.site_profile_service import SiteProfileService
from app.services.strategy_service import StrategyService
from app.tools.base import BaseTool, ToolResult
from app.utils.code_parser import clean_code

_URL_RE = re.compile(r'https?://[^\s"\'\>)]+', re.IGNORECASE)


class RepairScriptTool(BaseTool):
    """Wraps LLMService.repair_script as an agent-callable tool.

    When an AgentMemoryService is provided, the tool searches for similar
    past failures and injects the historical experience into the repair
    prompt so the LLM can leverage prior fixes.
    """

    def __init__(
        self,
        llm_service,
        strategy_service: StrategyService | None = None,
        memory_service=None,
        adaptive_strategy_service=None,
        site_profile_service: SiteProfileService | None = None,
    ) -> None:
        self._llm_service = llm_service
        self._strategy_service = strategy_service or StrategyService()
        self._diagnostic_service = FailureDiagnosticService()
        self._memory = memory_service
        self._adaptive = adaptive_strategy_service
        self._site_profile_service = site_profile_service

    @property
    def name(self) -> str:
        return "repair_script"

    @property
    def description(self) -> str:
        return (
            "Repair a failed Python Selenium script using the LLM. Provide the "
            "original prompt, the failed code, stderr/stdout, and optional RAG "
            "context. Returns the repaired code."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The original user test-scenario description.",
                },
                "original_code": {
                    "type": "string",
                    "description": "The Python Selenium code that failed.",
                },
                "error": {
                    "type": "string",
                    "description": "Stderr or exception text from the failed execution.",
                },
                "logs": {
                    "type": "string",
                    "description": "Stdout from the failed execution.",
                },
                "context": {
                    "type": "string",
                    "description": "RAG knowledge context to aid repair.",
                },
            },
            "required": ["prompt", "original_code", "error"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        prompt: str = kwargs["prompt"]
        original_code: str = kwargs["original_code"]
        error: str = kwargs["error"]
        logs: str = kwargs.get("logs", "")
        context: str = kwargs.get("context", "")

        try:
            strategy_decision = self._strategy_service.analyze_repair(
                prompt=prompt,
                error=error,
                original_code=original_code,
            )

            # Use adaptive strategy if available
            if self._adaptive is not None:
                adaptive_decision = self._adaptive.select_strategy(
                    error=error,
                    logs=logs,
                    code=original_code,
                    prompt=prompt,
                )
                failure_diagnosis = adaptive_decision.diagnosis.to_legacy()
                repair_guidance = (
                    self._strategy_service.build_repair_guidance(strategy_decision)
                    + "\n\n" + adaptive_decision.combined_guidance
                ).strip()
                memory_context = adaptive_decision.memory_context
            else:
                failure_diagnosis = self._diagnostic_service.diagnose(
                    error=error,
                    logs=logs,
                )
                repair_guidance = self._strategy_service.build_repair_guidance(strategy_decision)
                # Inject historical experience from agent memory
                memory_context = self._search_memory(error=error, prompt=prompt)

            site_profile_block = self._get_site_profile_block(prompt)
            raw_output = self._llm_service.repair_script(
                prompt=prompt,
                original_code=original_code,
                error=error,
                logs=logs,
                context=context,
                failure_diagnosis=failure_diagnosis,
                repair_guidance=repair_guidance,
                repair_strategy_block=self._strategy_service.build_repair_strategy_block(strategy_decision),
                memory_context=memory_context,
                site_profile_block=site_profile_block,
            )
            repaired_code = clean_code(raw_output).strip()
            if not repaired_code:
                return ToolResult(
                    success=False,
                    error="Repair returned empty code after cleanup.",
                )
            return ToolResult(
                success=True,
                data={
                    "repaired_code": repaired_code,
                    "strategy_before": strategy_decision.strategy_before,
                    "strategy_after": strategy_decision.strategy_after,
                    "failure_type": failure_diagnosis.failure_type,
                },
                summary=(
                    f"Repaired script ({len(repaired_code.splitlines())} lines). "
                    f"Diagnosis: {failure_diagnosis.failure_type}."
                ),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Memory / site-profile helpers
    # ------------------------------------------------------------------

    def _get_site_profile_block(self, prompt: str) -> str:
        """Extract target URL from *prompt* and return the profile block."""
        if self._site_profile_service is None:
            return ""
        m = _URL_RE.search(prompt)
        if not m:
            return ""
        return self._site_profile_service.get_profile_prompt_block(m.group(0))

    def _search_memory(self, *, error: str, prompt: str) -> str:
        """Search agent memory for similar past failures and return context."""
        if self._memory is None:
            return ""
        try:
            query = f"failure: {error[:500]} scenario: {prompt[:300]}"
            result = self._memory.search_similar(query=query, n_results=3, card_type="heal")
            if result.result_count == 0:
                return ""
            return result.context
        except Exception:
            return ""
