"""Agent tool framework: BaseTool abstract class and ToolRegistry."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("autotest.tools")


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Standardised return value from every tool invocation."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    summary: str = ""

    def to_observation(self, max_chars: int = 4000) -> str:
        """Render a compact string suitable for injection into the LLM context."""
        if not self.success:
            return f"[Tool Error] {self.error or 'Unknown error'}"
        text = self.summary or json.dumps(self.data, ensure_ascii=False, default=str)
        if len(text) > max_chars:
            return text[: max_chars - 3] + "..."
        return text


class BaseTool(ABC):
    """Interface every agent-callable tool must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier used by the LLM to select this tool."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-/LLM-readable description of what this tool does."""

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema describing the tool's input parameters.

        Must follow the OpenAI function-calling ``parameters`` format::

            {
                "type": "object",
                "properties": { ... },
                "required": [ ... ]
            }
        """

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool with the supplied keyword arguments and return a result."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def to_function_schema(self) -> dict[str, Any]:
        """Return the OpenAI-compatible function definition dict."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class ToolRegistry:
    """Central registry that holds all tools available to the agent."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            logger.warning("Overwriting previously registered tool %s", tool.name)
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def to_function_schemas(self) -> list[dict[str, Any]]:
        """Return a list of OpenAI-compatible tool schemas for all registered tools."""
        return [tool.to_function_schema() for tool in self._tools.values()]

    def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Look up a tool by *name* and call it with *arguments*."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {name}",
            )
        try:
            return tool.execute(**arguments)
        except Exception as exc:
            logger.exception("Tool %s raised an exception", name)
            return ToolResult(
                success=False,
                error=f"Tool {name} failed: {exc}",
            )
