# Success Pattern: Assuming a Selenium WebDriver instance named 'driver' is already on Baidu homepage (https://www.b...

Keywords: agent_memory, self-heal, healed_completed, first_success, Assuming, Selenium, WebDriver, instance, named, driver, already, Baidu, homepage, https://www.baidu.com, WebDriverWait, 10-second, timeout, locate, search, input, field, CSS, selector, #kw, click, focus, clear, existing, text, type.

## 场景
Assuming a Selenium WebDriver instance named 'driver' is already on Baidu homepage (https://www.baidu.com), use WebDriverWait with 10-second timeout to locate the search input field by CSS selector '#kw', click it to focus, clear any existing text, type the text 'DeepSeek' into it, then verify that the input's value attribute equals 'DeepSeek'. Do not navigate away or click the search button. Include proper imports and use the existing driver variable.

## 成功策略
首次执行即通过，以下脚本和选择器经验证稳定。

## 稳定选择器
- CSS_SELECTOR=#kw

## 执行元数据
- execution_id: `30dbb313-bb0c-4eed-bbe1-7e08f8ec3fec`
- card_type: `success`
