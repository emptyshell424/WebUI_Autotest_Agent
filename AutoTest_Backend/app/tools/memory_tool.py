"""Tool: search agent long-term memory for similar experiences."""

from __future__ import annotations

from typing import Any

from app.services.agent_memory_service import AgentMemoryService
from app.tools.base import BaseTool, ToolResult


class SearchMemoryTool(BaseTool):
    """Wraps AgentMemoryService.search_similar as an agent-callable tool."""

    def __init__(self, memory_service: AgentMemoryService) -> None:
        self._memory = memory_service

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return (
            "Search the agent's long-term memory for similar past experiences. "
            "Returns relevant memory cards including previous repair lessons, "
            "success patterns, and known traps. Use this before repairing a "
            "failed script to check if a similar failure has been fixed before."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A natural-language description of the current situation. "
                        "Include the failure type, error message, and scenario context."
                    ),
                },
                "n_results": {
                    "type": "integer",
                    "description": "Maximum number of memory cards to return (default 3).",
                },
                "card_type": {
                    "type": "string",
                    "enum": ["heal", "success", "trap"],
                    "description": "Optional filter: 'heal' for repair lessons, 'success' for success patterns, 'trap' for known traps.",
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        query: str = kwargs.get("query", "")
        n_results: int = kwargs.get("n_results", 3)
        card_type: str | None = kwargs.get("card_type")

        if not query.strip():
            return ToolResult(success=False, error="Query must not be empty.")

        try:
            result = self._memory.search_similar(
                query=query,
                n_results=n_results,
                card_type=card_type,
            )
            if result.result_count == 0:
                return ToolResult(
                    success=True,
                    data={"cards": [], "result_count": 0},
                    summary="No similar experiences found in memory.",
                )
            return ToolResult(
                success=True,
                data={
                    "cards": [
                        {
                            "source": c["source"],
                            "card_type": c["card_type"],
                            "distance": c.get("distance", 0),
                            "content_preview": c["content"][:500],
                        }
                        for c in result.cards
                    ],
                    "context": result.context,
                    "result_count": result.result_count,
                },
                summary=f"Found {result.result_count} relevant memory card(s).",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
