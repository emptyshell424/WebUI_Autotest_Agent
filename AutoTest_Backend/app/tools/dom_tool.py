"""Tool: analyse the current page DOM and return a structured summary."""

from __future__ import annotations

from typing import Any, Callable

from app.services.dom_observer import DOMObserver
from app.tools.base import BaseTool, ToolResult


class AnalyzePageDOMTool(BaseTool):
    """Agent-callable tool that captures a structured page-state snapshot.

    Requires a *driver_provider* — a callable that returns the active
    Selenium ``WebDriver`` instance (or ``None`` if no driver is available).
    """

    def __init__(
        self,
        driver_provider: Callable[[], Any | None],
        dom_observer: DOMObserver | None = None,
    ) -> None:
        self._driver_provider = driver_provider
        self._observer = dom_observer or DOMObserver()

    @property
    def name(self) -> str:
        return "analyze_page_dom"

    @property
    def description(self) -> str:
        return (
            "Capture the current page's DOM state: title, URL, visible text, "
            "interactive elements, forms, and error indicators. Returns a "
            "compact text summary suitable for reasoning about page content."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "Optional URL to navigate to before capturing. "
                        "If omitted, the current page is analysed."
                    ),
                },
                "max_chars": {
                    "type": "integer",
                    "description": (
                        "Maximum characters for the summary block (default 3000)."
                    ),
                },
            },
            "required": [],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        driver = self._driver_provider()
        if driver is None:
            return ToolResult(
                success=False,
                error="No active WebDriver session available.",
            )

        url: str | None = kwargs.get("url")
        max_chars: int = int(kwargs.get("max_chars", 3000))

        try:
            if url:
                driver.get(url)

            state = self._observer.capture_page_state(driver)
            summary = state.to_prompt_block(max_chars=max_chars)

            return ToolResult(
                success=True,
                data={
                    "title": state.title,
                    "url": state.url,
                    "interactive_element_count": len(state.interactive_elements),
                    "form_count": len(state.forms),
                    "error_count": len(state.error_indicators),
                },
                summary=summary,
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"DOM analysis failed: {exc}")
