# Web UI Test Patterns

1. Login flow: open the login page, wait for username and password inputs, fill them, submit, then assert on a post-login anchor.
2. Search flow: open the search page, wait for the input, enter the keyword, submit with ENTER if reliable, then assert the results container.
3. Form flow: wait for each required field before filling it, submit once, then assert on the confirmation message or page state change.
4. Table flow: locate the row by a stable cell value, then find the action button inside that row instead of clicking a global button.
5. Self-healing should preserve the original test intent and only adjust selectors, waits, page anchors, or context switching.
