"""Tests for TakeScreenshotTool."""

from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.tools.base import ToolRegistry
from app.tools.screenshot_tool import TakeScreenshotTool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTakeScreenshotTool(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def _make_driver(self, *, png_bytes: bytes = b"\x89PNG_FAKE") -> MagicMock:
        driver = MagicMock()

        def _save(path: str) -> bool:
            Path(path).write_bytes(png_bytes)
            return True

        driver.save_screenshot = MagicMock(side_effect=_save)
        return driver

    def test_schema_properties(self):
        tool = TakeScreenshotTool(driver_provider=lambda: None)
        self.assertEqual(tool.name, "take_screenshot")
        self.assertIn("filename", tool.parameters_schema["properties"])
        self.assertIn("return_base64", tool.parameters_schema["properties"])

    def test_no_driver(self):
        tool = TakeScreenshotTool(driver_provider=lambda: None)
        result = tool.execute()
        self.assertFalse(result.success)
        self.assertIn("No active WebDriver", result.error)

    def test_save_default_filename(self):
        driver = self._make_driver()
        tool = TakeScreenshotTool(
            driver_provider=lambda: driver,
            screenshot_dir=self._tmpdir,
        )
        result = tool.execute()
        self.assertTrue(result.success)
        self.assertIn("filepath", result.data)
        saved = Path(result.data["filepath"])
        self.assertTrue(saved.exists())
        self.assertEqual(saved.name, "screenshot.png")

    def test_save_custom_filename(self):
        driver = self._make_driver()
        tool = TakeScreenshotTool(
            driver_provider=lambda: driver,
            screenshot_dir=self._tmpdir,
        )
        result = tool.execute(filename="my_capture.png")
        self.assertTrue(result.success)
        saved = Path(result.data["filepath"])
        self.assertEqual(saved.name, "my_capture.png")

    def test_base64_not_returned_by_default(self):
        driver = self._make_driver()
        tool = TakeScreenshotTool(
            driver_provider=lambda: driver,
            screenshot_dir=self._tmpdir,
        )
        result = tool.execute()
        self.assertTrue(result.success)
        self.assertNotIn("base64", result.data)

    def test_base64_returned_when_requested(self):
        png_data = b"\x89PNG_TEST_DATA"
        driver = self._make_driver(png_bytes=png_data)
        tool = TakeScreenshotTool(
            driver_provider=lambda: driver,
            screenshot_dir=self._tmpdir,
        )
        result = tool.execute(return_base64=True)
        self.assertTrue(result.success)
        self.assertIn("base64", result.data)
        decoded = base64.b64decode(result.data["base64"])
        self.assertEqual(decoded, png_data)

    def test_driver_exception_caught(self):
        driver = MagicMock()
        driver.save_screenshot = MagicMock(side_effect=Exception("screenshot error"))
        tool = TakeScreenshotTool(
            driver_provider=lambda: driver,
            screenshot_dir=self._tmpdir,
        )
        result = tool.execute()
        self.assertFalse(result.success)
        self.assertIn("Screenshot failed", result.error)

    def test_creates_directory_if_missing(self):
        subdir = Path(self._tmpdir) / "sub" / "shots"
        self.assertFalse(subdir.exists())
        driver = self._make_driver()
        tool = TakeScreenshotTool(
            driver_provider=lambda: driver,
            screenshot_dir=subdir,
        )
        result = tool.execute()
        self.assertTrue(result.success)
        self.assertTrue(subdir.exists())

    def test_summary_contains_path(self):
        driver = self._make_driver()
        tool = TakeScreenshotTool(
            driver_provider=lambda: driver,
            screenshot_dir=self._tmpdir,
        )
        result = tool.execute()
        self.assertIn("Screenshot saved", result.summary)

    def test_register_in_registry(self):
        tool = TakeScreenshotTool(driver_provider=lambda: None)
        registry = ToolRegistry()
        registry.register(tool)
        self.assertIn("take_screenshot", registry.list_names())


if __name__ == "__main__":
    unittest.main()
