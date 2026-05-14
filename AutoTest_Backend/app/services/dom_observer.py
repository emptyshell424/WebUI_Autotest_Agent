"""DOM observation service: extract structured page state for LLM consumption.

Extracts only the information an LLM needs (interactive elements, error indicators,
visible text) without dumping the full DOM tree, keeping token usage under control.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("autotest.dom_observer")

try:
    from selenium.webdriver.common.by import By
except ImportError:
    class By:  # type: ignore[no-redef]
        CSS_SELECTOR = "css selector"
        XPATH = "xpath"

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

_INTERACTIVE_SELECTORS = (
    "a[href]",
    "button",
    "input",
    "select",
    "textarea",
    "[role='button']",
    "[role='link']",
    "[role='tab']",
    "[role='menuitem']",
    "[onclick]",
    "[contenteditable='true']",
)

_ERROR_INDICATORS_XPATH = (
    "//*[contains(@class,'error') or contains(@class,'Error') "
    "or contains(@class,'alert-danger') or contains(@class,'alert-error') "
    "or contains(@class,'invalid') or contains(@class,'fail') "
    "or contains(@role,'alert')]"
)

_VISIBLE_TEXT_MAX = 2000
_MAX_INTERACTIVE_ELEMENTS = 80
_MAX_ERROR_INDICATORS = 20


@dataclass(slots=True)
class InteractiveElement:
    """One interactive element on the page."""

    tag: str
    id: str = ""
    name: str = ""
    type: str = ""
    placeholder: str = ""
    text: str = ""
    aria_label: str = ""
    value: str = ""
    href: str = ""

    def selector_priority(self) -> int:
        """Lower number = higher priority for sorting."""
        if self.id:
            return 0
        if self.name:
            return 1
        if self.placeholder:
            return 2
        if self.aria_label:
            return 3
        return 4


@dataclass(slots=True)
class FormInfo:
    """Extracted form structure."""

    id: str = ""
    name: str = ""
    action: str = ""
    method: str = ""
    fields: list[dict[str, str]] = field(default_factory=list)


def _format_interactive_element(ie: InteractiveElement) -> str:
    """Format a single interactive element as a compact one-line description."""
    parts = [f"  <{ie.tag}"]
    if ie.id:
        parts.append(f'id="{ie.id}"')
    if ie.name:
        parts.append(f'name="{ie.name}"')
    if ie.type:
        parts.append(f'type="{ie.type}"')
    if ie.placeholder:
        parts.append(f'placeholder="{ie.placeholder}"')
    if ie.aria_label:
        parts.append(f'aria-label="{ie.aria_label}"')
    if ie.href:
        href_display = ie.href[:80] + ("..." if len(ie.href) > 80 else "")
        parts.append(f'href="{href_display}"')
    if ie.value:
        parts.append(f'value="{ie.value[:50]}"')
    result = " ".join(parts) + ">"
    if ie.text:
        result += f" {ie.text[:60]}"
    return result


@dataclass(slots=True)
class PageState:
    """Structured snapshot of the current page."""

    title: str = ""
    url: str = ""
    visible_text: str = ""
    interactive_elements: list[InteractiveElement] = field(default_factory=list)
    forms: list[FormInfo] = field(default_factory=list)
    error_indicators: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Prompt-block serialisation
    # ------------------------------------------------------------------ #

    def to_prompt_block(self, max_chars: int = 3000) -> str:
        """Compress this :class:`PageState` into a text block for LLM injection.

        Truncation strategy (layered):
        1. Build header (title + url) — always included.
        2. Error indicators — always included (critical signal).
        3. Interactive elements sorted by priority; low-priority items
           dropped first when budget is tight.
        4. Forms summary.
        5. Visible text — first to be cut when space runs low.
        """
        parts: list[str] = []

        # -- header -------------------------------------------------------
        header = f"[Page] {self.title}  ({self.url})"
        parts.append(header)

        # -- errors (high priority) ----------------------------------------
        if self.error_indicators:
            err_block = "[Errors]\n" + "\n".join(
                f"  - {e}" for e in self.error_indicators
            )
            parts.append(err_block)

        # -- interactive elements ------------------------------------------
        if self.interactive_elements:
            elem_lines: list[str] = []
            # Already sorted by priority in capture_page_state; iterate in
            # that order so high-priority items survive truncation.
            for ie in self.interactive_elements:
                line = _format_interactive_element(ie)
                elem_lines.append(line)
            elem_block = "[Interactive Elements]\n" + "\n".join(elem_lines)
            parts.append(elem_block)

        # -- forms ---------------------------------------------------------
        if self.forms:
            form_lines: list[str] = []
            for fi in self.forms:
                desc = f"  <form id='{fi.id}' action='{fi.action}' method='{fi.method}'>"
                field_descs = ", ".join(
                    f"{f.get('tag','')}[name={f.get('name','')}]" for f in fi.fields
                )
                if field_descs:
                    desc += f" fields: {field_descs}"
                form_lines.append(desc)
            form_block = "[Forms]\n" + "\n".join(form_lines)
            parts.append(form_block)

        # -- visible text (lowest priority) --------------------------------
        if self.visible_text:
            parts.append(f"[Visible Text]\n{self.visible_text}")

        # -- assemble & layered truncation ---------------------------------
        result = "\n\n".join(parts)
        if len(result) <= max_chars:
            return result

        # Layer 1: trim visible text
        parts_no_text = [p for p in parts if not p.startswith("[Visible Text]")]
        trimmed = "\n\n".join(parts_no_text)
        remaining = max_chars - len(trimmed) - 20  # 20 for separator + label
        if remaining > 80 and self.visible_text:
            parts_no_text.append(
                f"[Visible Text]\n{self.visible_text[:remaining]}..."
            )
        result = "\n\n".join(parts_no_text)
        if len(result) <= max_chars:
            return result

        # Layer 2: trim low-priority interactive elements
        parts_trimmed: list[str] = []
        for p in parts_no_text:
            if p.startswith("[Interactive Elements]"):
                lines = p.split("\n")
                header_line = lines[0]
                elem_lines_raw = lines[1:]
                # Keep only high-priority elements (those with id/name)
                kept: list[str] = []
                for ln in elem_lines_raw:
                    kept.append(ln)
                    candidate = header_line + "\n" + "\n".join(kept)
                    if len("\n\n".join(parts_trimmed + [candidate])) > max_chars - 100:
                        kept.pop()
                        break
                if kept:
                    parts_trimmed.append(header_line + "\n" + "\n".join(kept))
            else:
                parts_trimmed.append(p)
        result = "\n\n".join(parts_trimmed)
        return result[:max_chars]


@dataclass(slots=True)
class ElementContext:
    """Contextual information about a specific element."""

    found: bool = False
    tag: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    text: str = ""
    nearby_elements: list[dict[str, str]] = field(default_factory=list)
    suggested_selectors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DOMObserver
# ---------------------------------------------------------------------------


class DOMObserver:
    """Extracts a structured page snapshot from a live WebDriver session."""

    def capture_page_state(self, driver: Any) -> PageState:
        """Extract a structured :class:`PageState` from *driver*.

        Parameters
        ----------
        driver:
            A Selenium ``WebDriver`` instance (or compatible mock).

        Returns
        -------
        PageState
            Structured snapshot ready for LLM consumption.
        """
        state = PageState()

        # -- basic metadata --------------------------------------------------
        try:
            state.title = driver.title or ""
        except Exception:
            logger.debug("Failed to read driver.title")

        try:
            state.url = driver.current_url or ""
        except Exception:
            logger.debug("Failed to read driver.current_url")

        # -- visible text (truncated) ----------------------------------------
        try:
            body_text: str = driver.execute_script(
                "return document.body ? document.body.innerText : '';"
            ) or ""
            # Collapse whitespace
            body_text = re.sub(r"\s+", " ", body_text).strip()
            state.visible_text = body_text[:_VISIBLE_TEXT_MAX]
        except Exception:
            logger.debug("Failed to extract visible text via JS")

        # -- interactive elements --------------------------------------------
        state.interactive_elements = self._extract_interactive_elements(driver)

        # -- forms ------------------------------------------------------------
        state.forms = self._extract_forms(driver)

        # -- error indicators -------------------------------------------------
        state.error_indicators = self._extract_error_indicators(driver)

        return state

    # ------------------------------------------------------------------ #
    # get_element_context
    # ------------------------------------------------------------------ #

    def get_element_context(self, driver: Any, selector: str) -> ElementContext:
        """Return contextual info about *selector* on the current page.

        Parameters
        ----------
        driver:
            Selenium ``WebDriver`` instance.
        selector:
            CSS selector string.

        Returns
        -------
        ElementContext
        """
        ctx = ElementContext()
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            return ctx  # found=False

        if not elements:
            return ctx

        el = elements[0]
        ctx.found = True

        try:
            ctx.tag = el.tag_name or ""
        except Exception:
            pass

        # Attributes via JS
        try:
            attrs: dict[str, str] = driver.execute_script(
                "var items={}; var el=arguments[0]; "
                "for(var i=0;i<el.attributes.length;i++)"
                "{items[el.attributes[i].name]=el.attributes[i].value;} "
                "return items;",
                el,
            ) or {}
            ctx.attributes = attrs
        except Exception:
            pass

        try:
            ctx.text = (el.text or "")[:500]
        except Exception:
            pass

        # Nearby elements (parent + siblings)
        ctx.nearby_elements = self._get_nearby_elements(driver, el)

        # Suggested selectors
        ctx.suggested_selectors = self._suggest_selectors(ctx.tag, ctx.attributes, ctx.text)

        return ctx

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_interactive_elements(driver: Any) -> list[InteractiveElement]:
        """Find interactive elements via a combined CSS selector."""
        combined = ", ".join(_INTERACTIVE_SELECTORS)
        try:
            raw_elements = driver.find_elements(By.CSS_SELECTOR, combined)
        except Exception:
            logger.debug("Failed to query interactive elements")
            return []

        results: list[InteractiveElement] = []
        for el in raw_elements[:_MAX_INTERACTIVE_ELEMENTS]:
            try:
                ie = InteractiveElement(
                    tag=el.tag_name or "",
                    id=el.get_attribute("id") or "",
                    name=el.get_attribute("name") or "",
                    type=el.get_attribute("type") or "",
                    placeholder=el.get_attribute("placeholder") or "",
                    text=(el.text or "")[:200],
                    aria_label=el.get_attribute("aria-label") or "",
                    value=el.get_attribute("value") or "",
                    href=el.get_attribute("href") or "",
                )
                results.append(ie)
            except Exception:
                continue

        results.sort(key=lambda e: e.selector_priority())
        return results

    @staticmethod
    def _extract_forms(driver: Any) -> list[FormInfo]:
        """Extract form structures from the page."""
        try:
            form_elements = driver.find_elements(By.CSS_SELECTOR, "form")
        except Exception:
            return []

        forms: list[FormInfo] = []
        for form_el in form_elements[:10]:
            try:
                fi = FormInfo(
                    id=form_el.get_attribute("id") or "",
                    name=form_el.get_attribute("name") or "",
                    action=form_el.get_attribute("action") or "",
                    method=form_el.get_attribute("method") or "",
                )
                # Extract fields inside this form
                try:
                    fields_els = form_el.find_elements(
                        By.CSS_SELECTOR, "input, select, textarea"
                    )
                    for f_el in fields_els[:30]:
                        fi.fields.append({
                            "tag": f_el.tag_name or "",
                            "name": f_el.get_attribute("name") or "",
                            "type": f_el.get_attribute("type") or "",
                            "id": f_el.get_attribute("id") or "",
                        })
                except Exception:
                    pass

                forms.append(fi)
            except Exception:
                continue
        return forms

    @staticmethod
    def _extract_error_indicators(driver: Any) -> list[str]:
        """Find elements that look like error messages."""
        try:
            error_els = driver.find_elements(By.XPATH, _ERROR_INDICATORS_XPATH)
        except Exception:
            return []

        indicators: list[str] = []
        for el in error_els[:_MAX_ERROR_INDICATORS]:
            try:
                text = (el.text or "").strip()
                if text:
                    indicators.append(text[:300])
            except Exception:
                continue
        return indicators

    @staticmethod
    def _get_nearby_elements(driver: Any, element: Any) -> list[dict[str, str]]:
        """Return basic info about parent and adjacent siblings."""
        nearby: list[dict[str, str]] = []
        try:
            parent = driver.execute_script("return arguments[0].parentElement;", element)
            if parent:
                nearby.append({
                    "relation": "parent",
                    "tag": parent.tag_name or "",
                    "id": parent.get_attribute("id") or "",
                    "class": parent.get_attribute("class") or "",
                })
        except Exception:
            pass

        # Previous and next siblings
        for direction, js_prop in [("prev_sibling", "previousElementSibling"),
                                    ("next_sibling", "nextElementSibling")]:
            try:
                sibling = driver.execute_script(
                    f"return arguments[0].{js_prop};", element
                )
                if sibling:
                    nearby.append({
                        "relation": direction,
                        "tag": sibling.tag_name or "",
                        "id": sibling.get_attribute("id") or "",
                        "text": (sibling.text or "")[:100],
                    })
            except Exception:
                continue
        return nearby

    @staticmethod
    def _suggest_selectors(tag: str, attributes: dict[str, str], text: str) -> list[str]:
        """Generate candidate CSS selectors from element attributes."""
        selectors: list[str] = []
        el_id = attributes.get("id", "")
        name = attributes.get("name", "")
        placeholder = attributes.get("placeholder", "")
        aria_label = attributes.get("aria-label", "")

        if el_id:
            selectors.append(f"#{el_id}")
        if name:
            selectors.append(f"{tag}[name='{name}']")
        if placeholder:
            selectors.append(f"{tag}[placeholder='{placeholder}']")
        if aria_label:
            selectors.append(f"{tag}[aria-label='{aria_label}']")
        if text and len(text) < 60:
            # XPath-style text selector (informational)
            selectors.append(f"//{tag}[contains(text(),'{text[:40]}')]")
        return selectors
