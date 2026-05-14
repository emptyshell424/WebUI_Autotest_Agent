"""Tool: take a screenshot of the current browser page."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Callable

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger("autotest.tools.screenshot")


class TakeScreenshotTool(BaseTool):
    """Agent-callable tool that saves a screenshot of the active browser page.

    Requires a *driver_provider* callable returning the active WebDriver
    (or ``None`` when no session exists).

    A *screenshot_dir* can be provided to control where images are stored;
    otherwise a default ``screenshots/`` sub-directory is used.
    """

    def __init__(
        self,
        driver_provider: Callable[[], Any | None],
        screenshot_dir: Path | str | None = None,
    ) -> None:
        self._driver_provider = driver_provider
        self._screenshot_dir = Path(screenshot_dir) if screenshot_dir else Path("screenshots")

    @property
    def name(self) -> str:
        return "take_screenshot"

    @property
    def description(self) -> str:
        return (
            "Capture a screenshot of the current browser page. "
            "Returns the file path of the saved image. "
            "Optionally returns a base64-encoded version for multimodal models."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": (
                        "Optional filename for the screenshot (without directory). "
                        "Defaults to 'screenshot.png'."
                    ),
                },
                "return_base64": {
                    "type": "boolean",
                    "description": (
                        "If true, also return the image as a base64-encoded string. "
                        "Defaults to false."
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

        filename: str = kwargs.get("filename", "screenshot.png")
        return_base64: bool = bool(kwargs.get("return_base64", False))

        try:
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)
            filepath = self._screenshot_dir / filename

            driver.save_screenshot(str(filepath))

            data: dict[str, Any] = {"filepath": str(filepath)}

            if return_base64:
                raw = filepath.read_bytes()
                data["base64"] = base64.b64encode(raw).decode("ascii")

            logger.info("Screenshot saved to %s", filepath)
            return ToolResult(
                success=True,
                data=data,
                summary=f"Screenshot saved: {filepath}",
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"Screenshot failed: {exc}")
