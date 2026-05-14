"""Tests for DOMObserver – page state extraction with mocked WebDriver."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from app.services.dom_observer import (
    DOMObserver,
    ElementContext,
    FormInfo,
    InteractiveElement,
    PageState,
    _VISIBLE_TEXT_MAX,
    _format_interactive_element,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_mock_element(
    tag: str = "input",
    *,
    el_id: str = "",
    name: str = "",
    el_type: str = "",
    placeholder: str = "",
    text: str = "",
    aria_label: str = "",
    value: str = "",
    href: str = "",
    cls: str = "",
) -> MagicMock:
    """Build a mock Selenium WebElement."""
    el = MagicMock()
    el.tag_name = tag
    el.text = text

    attr_map = {
        "id": el_id,
        "name": name,
        "type": el_type,
        "placeholder": placeholder,
        "aria-label": aria_label,
        "value": value,
        "href": href,
        "class": cls,
        "action": "",
        "method": "",
    }
    el.get_attribute = MagicMock(side_effect=lambda a: attr_map.get(a, ""))
    el.find_elements = MagicMock(return_value=[])
    return el


def _make_mock_driver(
    *,
    title: str = "Test Page",
    url: str = "https://example.com",
    body_text: str = "Hello World",
    interactive: list[MagicMock] | None = None,
    form_elements: list[MagicMock] | None = None,
    error_elements: list[MagicMock] | None = None,
) -> MagicMock:
    """Build a mock Selenium WebDriver."""
    driver = MagicMock()
    driver.title = title
    driver.current_url = url

    def _execute_script(script, *args):
        if "innerText" in script:
            return body_text
        if "parentElement" in script:
            return None
        if "previousElementSibling" in script:
            return None
        if "nextElementSibling" in script:
            return None
        if "attributes" in script and args:
            return {"id": "el1", "name": "username"}
        return None

    driver.execute_script = MagicMock(side_effect=_execute_script)

    interactive = interactive if interactive is not None else []
    form_elements = form_elements if form_elements is not None else []
    error_elements = error_elements if error_elements is not None else []

    def _find_elements(by, selector):
        if "form" == selector:
            return form_elements
        if "alert" in selector or "error" in selector.lower():
            return error_elements
        # Default: interactive elements
        return interactive

    driver.find_elements = MagicMock(side_effect=_find_elements)
    return driver


# ---------------------------------------------------------------------------
# Tests: PageState & InteractiveElement data classes
# ---------------------------------------------------------------------------


class TestDataClasses(unittest.TestCase):
    def test_page_state_defaults(self):
        ps = PageState()
        self.assertEqual(ps.title, "")
        self.assertEqual(ps.url, "")
        self.assertEqual(ps.visible_text, "")
        self.assertEqual(ps.interactive_elements, [])
        self.assertEqual(ps.forms, [])
        self.assertEqual(ps.error_indicators, [])

    def test_interactive_element_priority_with_id(self):
        el = InteractiveElement(tag="input", id="user")
        self.assertEqual(el.selector_priority(), 0)

    def test_interactive_element_priority_with_name(self):
        el = InteractiveElement(tag="input", name="user")
        self.assertEqual(el.selector_priority(), 1)

    def test_interactive_element_priority_with_placeholder(self):
        el = InteractiveElement(tag="input", placeholder="Enter name")
        self.assertEqual(el.selector_priority(), 2)

    def test_interactive_element_priority_with_aria_label(self):
        el = InteractiveElement(tag="button", aria_label="Submit")
        self.assertEqual(el.selector_priority(), 3)

    def test_interactive_element_priority_bare(self):
        el = InteractiveElement(tag="a")
        self.assertEqual(el.selector_priority(), 4)

    def test_element_context_defaults(self):
        ctx = ElementContext()
        self.assertFalse(ctx.found)
        self.assertEqual(ctx.tag, "")
        self.assertEqual(ctx.suggested_selectors, [])


# ---------------------------------------------------------------------------
# Tests: capture_page_state
# ---------------------------------------------------------------------------


class TestCapturePageState(unittest.TestCase):
    def setUp(self):
        self.observer = DOMObserver()

    def test_basic_metadata(self):
        driver = _make_mock_driver(title="My Title", url="https://test.com")
        state = self.observer.capture_page_state(driver)
        self.assertEqual(state.title, "My Title")
        self.assertEqual(state.url, "https://test.com")

    def test_visible_text_extracted(self):
        driver = _make_mock_driver(body_text="Some visible text here")
        state = self.observer.capture_page_state(driver)
        self.assertIn("Some visible text", state.visible_text)

    def test_visible_text_truncated(self):
        long_text = "a" * (_VISIBLE_TEXT_MAX + 500)
        driver = _make_mock_driver(body_text=long_text)
        state = self.observer.capture_page_state(driver)
        self.assertLessEqual(len(state.visible_text), _VISIBLE_TEXT_MAX)

    def test_whitespace_collapsed_in_visible_text(self):
        driver = _make_mock_driver(body_text="hello   \n\n  world   ")
        state = self.observer.capture_page_state(driver)
        self.assertEqual(state.visible_text, "hello world")

    def test_interactive_elements_extracted(self):
        btn = _make_mock_element("button", el_id="submit-btn", text="Submit")
        inp = _make_mock_element("input", name="email", el_type="email")
        driver = _make_mock_driver(interactive=[btn, inp])
        state = self.observer.capture_page_state(driver)
        self.assertEqual(len(state.interactive_elements), 2)
        # sorted by priority: id first
        self.assertEqual(state.interactive_elements[0].id, "submit-btn")

    def test_interactive_elements_sorted_by_priority(self):
        bare = _make_mock_element("a", text="link")
        named = _make_mock_element("input", name="search")
        ided = _make_mock_element("button", el_id="go")
        driver = _make_mock_driver(interactive=[bare, named, ided])
        state = self.observer.capture_page_state(driver)
        tags_order = [e.tag for e in state.interactive_elements]
        # id (button) < name (input) < bare (a)
        self.assertEqual(tags_order, ["button", "input", "a"])

    def test_forms_extracted(self):
        form_el = _make_mock_element("form", el_id="login-form")
        field1 = _make_mock_element("input", name="user", el_type="text")
        form_el.find_elements = MagicMock(return_value=[field1])
        form_el.get_attribute = MagicMock(
            side_effect=lambda a: {"id": "login-form", "name": "", "action": "/login", "method": "POST"}.get(a, "")
        )
        driver = _make_mock_driver(form_elements=[form_el])
        state = self.observer.capture_page_state(driver)
        self.assertEqual(len(state.forms), 1)
        self.assertEqual(state.forms[0].id, "login-form")
        self.assertEqual(state.forms[0].action, "/login")
        self.assertEqual(len(state.forms[0].fields), 1)

    def test_error_indicators_extracted(self):
        err = _make_mock_element("div", cls="error", text="Username is required")
        driver = _make_mock_driver(error_elements=[err])
        state = self.observer.capture_page_state(driver)
        self.assertEqual(len(state.error_indicators), 1)
        self.assertIn("Username is required", state.error_indicators[0])

    def test_empty_error_text_ignored(self):
        err = _make_mock_element("div", cls="error", text="")
        driver = _make_mock_driver(error_elements=[err])
        state = self.observer.capture_page_state(driver)
        self.assertEqual(len(state.error_indicators), 0)

    def test_driver_exception_graceful(self):
        """If the driver raises exceptions, capture_page_state still returns a PageState."""
        driver = MagicMock()
        type(driver).title = PropertyMock(side_effect=Exception("no title"))
        type(driver).current_url = PropertyMock(side_effect=Exception("no url"))
        driver.execute_script = MagicMock(side_effect=Exception("js fail"))
        driver.find_elements = MagicMock(side_effect=Exception("find fail"))

        state = self.observer.capture_page_state(driver)
        self.assertIsInstance(state, PageState)
        self.assertEqual(state.title, "")
        self.assertEqual(state.url, "")

    def test_none_body_text_handled(self):
        driver = _make_mock_driver()
        driver.execute_script = MagicMock(return_value=None)
        driver.find_elements = MagicMock(return_value=[])
        state = self.observer.capture_page_state(driver)
        self.assertEqual(state.visible_text, "")


# ---------------------------------------------------------------------------
# Tests: get_element_context
# ---------------------------------------------------------------------------


class TestGetElementContext(unittest.TestCase):
    def setUp(self):
        self.observer = DOMObserver()

    def test_element_not_found(self):
        driver = MagicMock()
        driver.find_elements = MagicMock(return_value=[])
        ctx = self.observer.get_element_context(driver, "#missing")
        self.assertFalse(ctx.found)

    def test_element_found_basic_info(self):
        el = _make_mock_element("input", el_id="user", name="username", text="")
        driver = MagicMock()
        driver.find_elements = MagicMock(return_value=[el])
        driver.execute_script = MagicMock(side_effect=lambda s, *a: (
            {"id": "user", "name": "username"} if "attributes" in s else None
        ))

        ctx = self.observer.get_element_context(driver, "#user")
        self.assertTrue(ctx.found)
        self.assertEqual(ctx.tag, "input")
        self.assertEqual(ctx.attributes.get("id"), "user")

    def test_suggested_selectors_generated(self):
        el = _make_mock_element("input", el_id="email", name="email", placeholder="Enter email")
        driver = MagicMock()
        driver.find_elements = MagicMock(return_value=[el])
        driver.execute_script = MagicMock(side_effect=lambda s, *a: (
            {"id": "email", "name": "email", "placeholder": "Enter email"} if "attributes" in s else None
        ))

        ctx = self.observer.get_element_context(driver, "#email")
        self.assertTrue(ctx.found)
        self.assertIn("#email", ctx.suggested_selectors)
        self.assertIn("input[name='email']", ctx.suggested_selectors)
        self.assertIn("input[placeholder='Enter email']", ctx.suggested_selectors)

    def test_nearby_elements_populated(self):
        el = _make_mock_element("input", el_id="field")
        parent = _make_mock_element("div", el_id="form-group")
        sibling = _make_mock_element("label", text="Name")

        driver = MagicMock()
        driver.find_elements = MagicMock(return_value=[el])

        def _exec_script(script, *args):
            if "parentElement" in script:
                return parent
            if "previousElementSibling" in script:
                return sibling
            if "nextElementSibling" in script:
                return None
            if "attributes" in script:
                return {"id": "field"}
            return None

        driver.execute_script = MagicMock(side_effect=_exec_script)

        ctx = self.observer.get_element_context(driver, "#field")
        self.assertTrue(ctx.found)
        relations = [n["relation"] for n in ctx.nearby_elements]
        self.assertIn("parent", relations)
        self.assertIn("prev_sibling", relations)

    def test_driver_find_raises(self):
        driver = MagicMock()
        driver.find_elements = MagicMock(side_effect=Exception("boom"))
        ctx = self.observer.get_element_context(driver, "div")
        self.assertFalse(ctx.found)

    def test_long_text_truncated(self):
        long_text = "x" * 1000
        el = _make_mock_element("div", text=long_text)
        driver = MagicMock()
        driver.find_elements = MagicMock(return_value=[el])
        driver.execute_script = MagicMock(return_value=None)

        ctx = self.observer.get_element_context(driver, "div")
        self.assertTrue(ctx.found)
        self.assertLessEqual(len(ctx.text), 500)


# ---------------------------------------------------------------------------
# Tests: _suggest_selectors helper
# ---------------------------------------------------------------------------


class TestSuggestSelectors(unittest.TestCase):
    def test_id_selector(self):
        s = DOMObserver._suggest_selectors("input", {"id": "foo"}, "")
        self.assertIn("#foo", s)

    def test_name_selector(self):
        s = DOMObserver._suggest_selectors("input", {"name": "bar"}, "")
        self.assertIn("input[name='bar']", s)

    def test_placeholder_selector(self):
        s = DOMObserver._suggest_selectors("input", {"placeholder": "Search..."}, "")
        self.assertIn("input[placeholder='Search...']", s)

    def test_aria_label_selector(self):
        s = DOMObserver._suggest_selectors("button", {"aria-label": "Close"}, "")
        self.assertIn("button[aria-label='Close']", s)

    def test_text_xpath_selector(self):
        s = DOMObserver._suggest_selectors("span", {}, "Click me")
        self.assertTrue(any("contains(text()," in sel for sel in s))

    def test_long_text_excluded(self):
        s = DOMObserver._suggest_selectors("div", {}, "a" * 100)
        self.assertFalse(any("contains(text()," in sel for sel in s))

    def test_empty_attrs_empty_text(self):
        s = DOMObserver._suggest_selectors("div", {}, "")
        self.assertEqual(s, [])


# ---------------------------------------------------------------------------
# Tests: _format_interactive_element helper
# ---------------------------------------------------------------------------


class TestFormatInteractiveElement(unittest.TestCase):
    def test_basic_formatting(self):
        ie = InteractiveElement(tag="input", id="user", name="username", type="text")
        line = _format_interactive_element(ie)
        self.assertIn('<input', line)
        self.assertIn('id="user"', line)
        self.assertIn('name="username"', line)
        self.assertIn('type="text"', line)

    def test_text_appended(self):
        ie = InteractiveElement(tag="button", id="go", text="Submit")
        line = _format_interactive_element(ie)
        self.assertTrue(line.endswith("Submit"))

    def test_long_href_truncated(self):
        ie = InteractiveElement(tag="a", href="https://example.com/" + "x" * 100)
        line = _format_interactive_element(ie)
        self.assertIn("...", line)

    def test_empty_element(self):
        ie = InteractiveElement(tag="div")
        line = _format_interactive_element(ie)
        self.assertIn("<div>", line)


# ---------------------------------------------------------------------------
# Tests: to_prompt_block (3.2 DOM summary compression)
# ---------------------------------------------------------------------------


class TestToPromptBlock(unittest.TestCase):
    def _make_state(self, **kwargs) -> PageState:
        return PageState(**kwargs)

    def test_empty_state(self):
        block = self._make_state().to_prompt_block()
        self.assertIn("[Page]", block)

    def test_contains_title_and_url(self):
        block = self._make_state(title="Login", url="https://app.com/login").to_prompt_block()
        self.assertIn("Login", block)
        self.assertIn("https://app.com/login", block)

    def test_contains_error_indicators(self):
        block = self._make_state(error_indicators=["Password required"]).to_prompt_block()
        self.assertIn("[Errors]", block)
        self.assertIn("Password required", block)

    def test_contains_interactive_elements(self):
        elems = [
            InteractiveElement(tag="input", id="user", type="text"),
            InteractiveElement(tag="button", text="Login"),
        ]
        block = self._make_state(interactive_elements=elems).to_prompt_block()
        self.assertIn("[Interactive Elements]", block)
        self.assertIn('id="user"', block)
        self.assertIn("Login", block)

    def test_contains_forms(self):
        forms = [FormInfo(id="login", action="/auth", method="POST",
                          fields=[{"tag": "input", "name": "user", "type": "text", "id": ""}])]
        block = self._make_state(forms=forms).to_prompt_block()
        self.assertIn("[Forms]", block)
        self.assertIn("login", block)
        self.assertIn("/auth", block)

    def test_contains_visible_text(self):
        block = self._make_state(visible_text="Welcome to the site").to_prompt_block()
        self.assertIn("[Visible Text]", block)
        self.assertIn("Welcome to the site", block)

    def test_respects_max_chars(self):
        block = self._make_state(
            title="T",
            url="https://x.com",
            visible_text="a" * 5000,
        ).to_prompt_block(max_chars=500)
        self.assertLessEqual(len(block), 500)

    def test_visible_text_trimmed_first(self):
        """When exceeding budget, visible_text is cut before elements."""
        elems = [InteractiveElement(tag="input", id=f"field_{i}") for i in range(10)]
        block = self._make_state(
            title="Test",
            url="https://x.com",
            interactive_elements=elems,
            visible_text="z" * 5000,
        ).to_prompt_block(max_chars=800)
        self.assertLessEqual(len(block), 800)
        # Elements should survive
        self.assertIn("[Interactive Elements]", block)
        # Visible text should be truncated (with ellipsis)
        self.assertIn("...", block)

    def test_elements_trimmed_when_too_many(self):
        """If even after cutting visible_text we exceed budget, low-priority elements get trimmed."""
        elems = [InteractiveElement(tag="a", text=f"Link {i}" + "x" * 50) for i in range(50)]
        block = self._make_state(
            title="Big Page",
            url="https://big.com",
            interactive_elements=elems,
        ).to_prompt_block(max_chars=400)
        self.assertLessEqual(len(block), 400)

    def test_no_truncation_when_fits(self):
        block = self._make_state(
            title="Small",
            url="https://s.com",
            visible_text="tiny",
            interactive_elements=[InteractiveElement(tag="button", id="ok")],
        ).to_prompt_block(max_chars=3000)
        self.assertNotIn("...", block)
        self.assertIn("[Visible Text]", block)

    def test_priority_order_preserved_in_block(self):
        """Elements with id should appear before elements without."""
        elems = [
            InteractiveElement(tag="a", text="bare link"),
            InteractiveElement(tag="input", id="top"),
        ]
        # Sort happens during capture_page_state, but to_prompt_block uses
        # the order as-is. Pre-sort for this test.
        elems.sort(key=lambda e: e.selector_priority())
        block = self._make_state(interactive_elements=elems).to_prompt_block()
        pos_top = block.index('id="top"')
        pos_bare = block.index("bare link")
        self.assertLess(pos_top, pos_bare)


if __name__ == "__main__":
    unittest.main()
