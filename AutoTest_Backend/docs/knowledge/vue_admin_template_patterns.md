# Vue Admin Template Patterns / vue-admin-template 模式

Keywords: vue-admin-template, 登录, Dashboard, Example, Example/Table, Table, 表格, Element UI Table, Title, Author, Pageviews, Status, Form, Activity name, Create, name: admin.

vue-admin-template uses `/login` for authentication and redirects to `/dashboard` after a successful login. The dashboard page is a stable success anchor and shows `name: Super Admin`.

中文 prompt “登录 vue-admin-template 后验证 Dashboard” 应命中本知识。生成脚本时应先完成真实登录动作，再断言 `Dashboard`、`/dashboard` 或 `name: Super Admin`，不能只断言点击了 Login。

The table demo lives under `Example` -> `Table`, with route `/example/table`. It renders an Element UI `<el-table>` and the important headers are `Title`, `Author`, `Pageviews`, and `Status`.

中文 prompt “打开 Example/Table 页面并验证表格列” 应命中本知识。生成脚本时应登录后进入 `/example/table`，等待 `.el-table` 可见并等待 loading 状态结束，再断言表头包含 `Title`、`Author`、`Pageviews`、`Status`，并至少确认一行数据存在。

Prefer visible text, route anchors, Element UI container classes such as `.el-table`, `.el-table__header`, and nearby table header cells before falling back to brittle absolute XPath.

## Critical Selector Rules (must follow, not break)

Login button:
- CORRECT: `By.CSS_SELECTOR, "button.el-button--primary"` or `By.XPATH, "//span[text()='Login']/parent::button"`
- WRONG: `button[type='submit']` — Element UI `<el-button>` always renders `type="button"`, NEVER `type="submit"`
- WRONG: `button:contains('Login')` — `:contains()` is jQuery syntax, not valid CSS selector
- WRONG: `//button[contains(text(),'Login')]` — text "Login" is inside `<span>` child, use `contains(., 'Login')` with dot instead

Username: use `By.NAME, "username"` or `By.CSS_SELECTOR, "input[name='username']"`
Password: use `By.NAME, "password"` or `By.CSS_SELECTOR, "input[name='password']"`

Dashboard post-login verification:
- CORRECT: `By.XPATH, "//*[contains(.,'Dashboard')]"` or `By.XPATH, "//*[contains(.,'Super Admin')]"` (display name is "Super Admin", NOT "admin")
- WRONG: `//*[contains(.,'name: admin')]` — the actual display name is "Super Admin", "name: admin" does NOT appear on the page
- WRONG: `//*[contains(text(),'admin')]` — `text()` only matches direct text nodes, misses text inside child elements
