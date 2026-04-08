# Selenium Tips

1. Prefer `WebDriverWait` with explicit conditions before interacting with dynamic elements.
2. Favor stable selectors such as `id`, `name`, and clear CSS selectors before XPath.
3. When an element is inside an `iframe`, switch into the frame before locating it.
4. After `driver.get(...)`, wait for a stable page anchor such as `body` or a known root element.
5. If a click is intercepted, try waiting for clickability before considering a JavaScript click fallback.
