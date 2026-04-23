# Explicit Wait Patterns / 显式等待模式

Keywords: WebDriverWait, explicit wait, 显式等待, visibility_of_element_located, element_to_be_clickable, presence_of_element_located, staleness_of.

Use `WebDriverWait(driver, timeout).until(EC.condition)` instead of `time.sleep()` or implicit waits. Common conditions:

- `visibility_of_element_located`: best before `send_keys()` or reading text.
- `element_to_be_clickable`: best before `click()`.
- `presence_of_element_located`: use when the element does not need to be visible yet.
- `staleness_of(old_element)`: wait for a page transition that removes a known element.
- `title_contains` or `url_contains`: verify navigation completed.

Chain waits: first wait for the page anchor, then wait for the target element. Avoid redundant waits on the same element.

在交互前使用 `WebDriverWait` + 显式条件，而非 `time.sleep()`。发送文本前用 `visibility_of_element_located`，点击前用 `element_to_be_clickable`。先等待页面锚点，再等待目标元素。
