"""Tests for AnalyzePageDOMTool."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.services.dom_observer import DOMObserver, InteractiveElement, PageState
from app.tools.base import ToolRegistry
from app.tools.dom_tool import AnalyzePageDOMTool


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_mock_driver(
    *,
    title: str = "Test Page",
    url: str = "https://example.com",
    body_text: str = "Hello",
) -> MagicMock:
    driver = MagicMock()
    driver.title = title
    driver.current_url = url
    driver.execute_script = MagicMock(side_effect=lambda s, *a: (
        body_text if "innerText" in s else None
    ))
    driver.find_elements = MagicMock(return_value=[])
    return driver


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnalyzePageDOMTool(unittest.TestCase):
    def test_schema_properties(self):
        tool = AnalyzePageDOMTool(driver_provider=lambda: None)
        self.assertEqual(tool.name, "analyze_page_dom")
        self.assertIn("url", tool.parameters_schema["properties"])
        schema = tool.to_function_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "analyze_page_dom")

    def test_no_driver_returns_error(self):
        tool = AnalyzePageDOMTool(driver_provider=lambda: None)
        result = tool.execute()
        self.assertFalse(result.success)
        self.assertIn("No active WebDriver", result.error)

    def test_capture_current_page(self):
        driver = _make_mock_driver(title="Login Page", url="https://app.com/login")
        tool = AnalyzePageDOMTool(driver_provider=lambda: driver)
        result = tool.execute()
        self.assertTrue(result.success)
        self.assertEqual(result.data["title"], "Login Page")
        self.assertEqual(result.data["url"], "https://app.com/login")
        self.assertIn("[Page]", result.summary)
        self.assertIn("Login Page", result.summary)

    def test_navigate_to_url(self):
        driver = _make_mock_driver()
        tool = AnalyzePageDOMTool(driver_provider=lambda: driver)
        result = tool.execute(url="https://other.com")
        self.assertTrue(result.success)
        driver.get.assert_called_once_with("https://other.com")

    def test_no_navigate_when_url_omitted(self):
        driver = _make_mock_driver()
        tool = AnalyzePageDOMTool(driver_provider=lambda: driver)
        result = tool.execute()
        self.assertTrue(result.success)
        driver.get.assert_not_called()

    def test_max_chars_respected(self):
        driver = _make_mock_driver(body_text="x" * 5000)
        tool = AnalyzePageDOMTool(driver_provider=lambda: driver)
        result = tool.execute(max_chars=200)
        self.assertTrue(result.success)
        self.assertLessEqual(len(result.summary), 200)

    def test_data_counts(self):
        btn = MagicMock()
        btn.tag_name = "button"
        btn.text = "Go"
        btn.get_attribute = MagicMock(side_effect=lambda a: {"id": "go-btn"}.get(a, ""))

        driver = _make_mock_driver()
        driver.find_elements = MagicMock(return_value=[btn])

        tool = AnalyzePageDOMTool(driver_provider=lambda: driver)
        result = tool.execute()
        self.assertTrue(result.success)
        self.assertIn("interactive_element_count", result.data)
        self.assertIn("form_count", result.data)
        self.assertIn("error_count", result.data)

    def test_driver_exception_caught(self):
        driver = MagicMock()
        driver.get = MagicMock(side_effect=Exception("connection refused"))
        tool = AnalyzePageDOMTool(driver_provider=lambda: driver)
        result = tool.execute(url="https://down.com")
        self.assertFalse(result.success)
        self.assertIn("DOM analysis failed", result.error)

    def test_register_in_registry(self):
        tool = AnalyzePageDOMTool(driver_provider=lambda: None)
        registry = ToolRegistry()
        registry.register(tool)
        self.assertIn("analyze_page_dom", registry.list_names())
        result = registry.invoke("analyze_page_dom", {})
        self.assertFalse(result.success)  # no driver

    def test_custom_dom_observer(self):
        """A custom DOMObserver can be injected."""
        mock_observer = MagicMock(spec=DOMObserver)
        mock_observer.capture_page_state.return_value = PageState(
            title="Custom", url="https://custom.com",
        )
        driver = _make_mock_driver()
        tool = AnalyzePageDOMTool(driver_provider=lambda: driver, dom_observer=mock_observer)
        result = tool.execute()
        self.assertTrue(result.success)
        self.assertEqual(result.data["title"], "Custom")
        mock_observer.capture_page_state.assert_called_once_with(driver)


if __name__ == "__main__":
    unittest.main()
