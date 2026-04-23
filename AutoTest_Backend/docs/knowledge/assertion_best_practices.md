# Assertion Best Practices / 断言最佳实践

Keywords: assert, 验证, 断言, Test Completed, 测试完成, success criteria, page state.

1. Assert on a visible page-state change (text content, URL, title, element presence), not on the absence of an error.
2. Place the success print `print('Test Completed')` immediately after the real assertion, not inside `finally` or before the assertion.
3. If verifying navigation, use `assert "expected" in driver.current_url` or `assert "expected" in driver.title`.
4. If verifying element content, read `.text` or `.get_attribute("value")` after waiting for visibility.
5. Avoid asserting on transient states like loading spinners or toast messages that auto-dismiss.
6. For forms, assert on the confirmation message or the updated list/table row rather than the submit button state.

在真正的页面状态变化上做断言，而不是在无错误上做断言。将 `print('Test Completed')` 放在断言之后，不要放在 `finally` 或断言之前。
