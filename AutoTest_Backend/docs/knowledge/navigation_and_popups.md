# Navigation, Tabs, and Popup Handling / 页面导航与弹窗处理

Keywords: navigation, 导航, new tab, 新标签页, window handle, alert, popup, 弹窗, switch_to.

1. After clicking a link that opens a new tab, switch to it with `driver.switch_to.window(driver.window_handles[-1])`.
2. After finishing in the new tab, close it with `driver.close()` and switch back: `driver.switch_to.window(driver.window_handles[0])`.
3. For JavaScript `alert()`, `confirm()`, or `prompt()` dialogs, use `driver.switch_to.alert` to accept, dismiss, or read text.
4. After `driver.get(new_url)`, wait for a known page anchor before continuing.
5. For single-page applications (SPA), navigation may not trigger a full page load. Wait for the route-specific element instead of `body`.
6. If the page has `iframe` elements, switch into the frame with `driver.switch_to.frame(...)` before locating child elements, and switch out with `driver.switch_to.default_content()`.

点击打开新标签页后，用 `switch_to.window` 切换；处理完后关闭并切回。JS 弹窗用 `switch_to.alert`。SPA 导航后等路由特定元素而非 `body`。
