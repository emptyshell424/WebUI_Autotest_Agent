"""Tool: search the RAG knowledge base."""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool, ToolResult


class SearchKnowledgeTool(BaseTool):
    """Wraps RAGService.search as an agent-callable tool."""

    def __init__(self, rag_service) -> None:
        self._rag_service = rag_service

    @property
    def name(self) -> str:
        return "search_knowledge"

    @property
    def description(self) -> str:
        return (
            "Search the project knowledge base for relevant documentation and past "
            "patterns. Returns matching context text and source documents."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query in natural language (Chinese or English).",
                },
                "retrieval_mode": {
                    "type": "string",
                    "enum": ["vector", "hybrid", "hybrid_rerank"],
                    "description": "Retrieval mode. Defaults to hybrid_rerank.",
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        query: str = kwargs["query"]
        retrieval_mode: str | None = kwargs.get("retrieval_mode")
        try:
            result = self._rag_service.search(query, retrieval_mode=retrieval_mode)
            return ToolResult(
                success=True,
                data={
                    "context": result.context,
                    "sources": result.sources,
                    "result_count": result.result_count,
                    "retrieval_mode": result.retrieval_mode,
                },
                summary=f"Found {result.result_count} knowledge chunks ({result.retrieval_mode}).",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
