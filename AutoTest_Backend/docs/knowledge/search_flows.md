# Search Flow Patterns / 搜索流程模式

Keywords: search, 搜索, 搜索框, keyword, result container, results page, 百度, Baidu, kw, input[name='wd'], #content_left, TimeoutException, Test Completed.

Default search semantics are interaction-first. When the user says "open Baidu and search for DeepSeek", the first generated script should preserve the homepage interaction flow: open `https://www.baidu.com`, locate the homepage search input, submit the keyword, then verify the results area.

默认搜索语义是交互优先。像“打开百度并搜索 DeepSeek”这类请求，首次生成的脚本应保留真实页面交互流程：打开 `https://www.baidu.com`，定位首页搜索框，提交关键词，然后验证结果区域。

For Baidu, the direct results-page URL `https://www.baidu.com/s?wd=<encoded keyword>` is a repair-only fallback unless the user explicitly asks for result-only verification. If homepage anchors such as `#kw` or `input[name='wd']` fail during self-heal and homepage interaction was not explicitly required, the repair path may downgrade from `interaction_first` to `result_first`.

对百度来说，`https://www.baidu.com/s?wd=<编码后的关键词>` 这种结果页直达路径默认只属于修复阶段的降级方案，除非用户明确要求“只验证结果”。如果自愈阶段发现首页锚点例如 `#kw` 或 `input[name='wd']` 失效，而用户又没有明确要求首页交互，则修复流程可以从 `interaction_first` 降级到 `result_first`。

When the Baidu repair path uses the results page, `urllib.parse.quote_plus` is allowed to encode the keyword. Wait for `body` and `#content_left`, then assert that at least one visible result link exists under `#content_left h3 a` before printing `print('Test Completed')`.

当百度修复路径使用结果页时，可以使用 `urllib.parse.quote_plus` 对关键词进行编码。脚本应等待 `body` 和 `#content_left`，然后断言 `#content_left h3 a` 下至少存在一个可见结果链接，最后再打印 `print('Test Completed')`。
