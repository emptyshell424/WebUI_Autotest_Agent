# Dynamic Pages and Async Loading

1. After `driver.get(...)`, wait for `body` or a page-specific root container before interacting with children.
2. Prefer `visibility_of_element_located` or `element_to_be_clickable` before `send_keys()` and `click()`.
3. If content loads after a spinner, wait for the spinner to disappear or the result container to become visible.
4. For search or list pages, assert on a stable result container instead of a transient loading indicator.
5. Timeout-related failures often improve when waits are moved closer to the real interaction point.
