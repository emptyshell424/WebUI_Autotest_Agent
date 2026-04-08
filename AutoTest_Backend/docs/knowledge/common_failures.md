# Common Selenium Failure Patterns

1. `NoSuchElementException`: verify the locator, page context, frame context, and whether the element is loaded yet.
2. `ElementClickInterceptedException`: wait for clickability, scroll the element into view, or close overlays before clicking.
3. `TimeoutException`: increase selector stability first; only increase waiting time after verifying the correct page anchor.
4. `StaleElementReferenceException`: relocate the element after the DOM refresh instead of reusing an old reference.
5. If the script prints success text before a later crash, move the final success print after the real assertion and before cleanup.
