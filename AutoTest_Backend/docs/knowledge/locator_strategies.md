# Locator Strategies

1. Prefer stable selectors such as `id`, `name`, `data-testid`, and short CSS selectors before using XPath.
2. Avoid brittle selectors that depend on long DOM chains or generated class names.
3. When a page uses repeated buttons, narrow the search to a nearby form, card, dialog, or table row.
4. If a selector fails after a UI change, try locating by visible text, semantic attributes, or a more stable page anchor.
5. For self-healing scenarios, compare the failing selector against nearby labels, placeholders, and button text before replacing it.
