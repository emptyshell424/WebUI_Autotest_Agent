# Safe Code Generation Rules / 安全代码生成规则

Keywords: safe import, 安全, import, sys, os, subprocess, pathlib, minimal imports, urllib, quote_plus.

Only import the Selenium modules required for the current test, plus minimal standard-library helpers that are directly required by the scenario. Do not import `sys`, `os`, `subprocess`, or `pathlib` for ordinary UI test generation.

只导入当前测试真正需要的 Selenium 模块，以及与当前场景直接相关的最小标准库辅助模块。普通 UI 测试生成时不要导入 `sys`、`os`、`subprocess` 或 `pathlib`。

`urllib.parse.quote_plus` is allowed when a repair flow must construct a search-results URL safely, such as a Baidu self-heal downgrade from `interaction_first` to `result_first`. This allowance is narrow and should not be expanded into arbitrary standard-library imports.

当修复流程必须安全构造搜索结果页 URL 时，例如百度自愈从 `interaction_first` 降级到 `result_first`，允许使用 `urllib.parse.quote_plus`。这个白名单是窄授权，不应被扩大成任意标准库导入。

Prefer a minimal, readable Selenium script: open the target page, wait for stable anchors, perform the requested interaction, assert the requested result, print `Test Completed`, and quit the driver in cleanup.

优先生成最小且可读的 Selenium 脚本：打开目标页面，等待稳定锚点，执行请求的交互，断言目标结果，打印 `Test Completed`，最后在清理阶段退出浏览器。
