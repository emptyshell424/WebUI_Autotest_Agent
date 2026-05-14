"""Tool: generate a Selenium test script from a natural-language prompt."""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool, ToolResult


class GenerateScriptTool(BaseTool):
    """Wraps GenerationService.generate as an agent-callable tool."""

    def __init__(self, generation_service) -> None:
        self._generation_service = generation_service

    @property
    def name(self) -> str:
        return "generate_selenium_script"

    @property
    def description(self) -> str:
        return (
            "Generate a runnable Python Selenium test script from a natural-language "
            "prompt. Returns the generated code, test case ID, and RAG knowledge "
            "sources used during generation."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Natural-language description of the test scenario (Chinese or English).",
                },
                "retrieval_mode": {
                    "type": "string",
                    "enum": ["vector", "hybrid", "hybrid_rerank"],
                    "description": "RAG retrieval mode. Defaults to hybrid_rerank if omitted.",
                },
            },
            "required": ["prompt"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        prompt: str = kwargs["prompt"]
        retrieval_mode: str | None = kwargs.get("retrieval_mode")
        try:
            record, rag_result = self._generation_service.generate(
                prompt, retrieval_mode=retrieval_mode
            )
            return ToolResult(
                success=True,
                data={
                    "test_case_id": record.id,
                    "generated_code": record.generated_code,
                    "knowledge_sources": rag_result.sources,
                    "retrieval_mode": rag_result.retrieval_mode,
                },
                summary=f"Generated {len(record.generated_code.splitlines())} lines of Selenium code (case {record.id}).",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
