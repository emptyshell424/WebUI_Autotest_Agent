# Bilingual UI Prompt Patterns / 中英双语 UI 提示模式

Keywords: 中文 prompt, Chinese prompt, 登录, 搜索, 输入框, 点击, 按钮, 验证, 提示信息, 表格, 表单, dashboard, table, form.

For Chinese prompts, map common UI phrases to stable Selenium actions. `打开登录页面` usually means calling `driver.get(...)` and waiting for login inputs. `输入用户名和密码` means waiting for input visibility before `clear()` and `send_keys()`. `验证进入首页` means asserting a stable post-login page anchor instead of only checking that a click happened.

对于中文 prompt，应把常见界面描述映射为稳定的 Selenium 行为。`打开登录页面` 通常表示调用 `driver.get(...)` 并等待登录输入框；`输入用户名和密码` 表示先等待输入框可见，再执行 `clear()` 和 `send_keys()`；`验证进入首页` 表示断言登录后的稳定页面锚点，而不是只检查点击动作。

`搜索` 或 `在搜索框输入关键词` 通常表示定位搜索输入框、输入关键词、提交搜索，再验证稳定的结果容器。默认情况下，这类描述仍然保留真实页面交互流程；只有当修复策略明确允许降级，或用户明确说“只验证结果”时，才可以跳过首页交互直接访问结果页。

`Search` or `type a keyword into the search box` usually means locating the search input, entering the keyword, submitting the search, and then verifying a stable results container. By default, these prompts still preserve the real page interaction flow. Only use a direct results URL when the repair strategy explicitly allows a downgrade or the user explicitly asks for result-only verification.
