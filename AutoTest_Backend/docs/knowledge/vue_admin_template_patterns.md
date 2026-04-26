# Vue Admin Template Patterns / vue-admin-template 模式

Keywords: vue-admin-template, 登录, Dashboard, Example, Example/Table, Table, 表格, Element UI Table, Title, Author, Pageviews, Status, Form, Activity name, Create, name: admin.

vue-admin-template uses `/login` for authentication and redirects to `/dashboard` after a successful login. The dashboard page is a stable success anchor and shows `name: admin`.

中文 prompt “登录 vue-admin-template 后验证 Dashboard” 应命中本知识。生成脚本时应先完成真实登录动作，再断言 `Dashboard`、`/dashboard` 或 `name: admin`，不能只断言点击了 Login。

The table demo lives under `Example` -> `Table`, with route `/example/table`. It renders an Element UI `<el-table>` and the important headers are `Title`, `Author`, `Pageviews`, and `Status`.

中文 prompt “打开 Example/Table 页面并验证表格列” 应命中本知识。生成脚本时应登录后进入 `/example/table`，等待 `.el-table` 可见并等待 loading 状态结束，再断言表头包含 `Title`、`Author`、`Pageviews`、`Status`，并至少确认一行数据存在。

Prefer visible text, route anchors, Element UI container classes such as `.el-table`, `.el-table__header`, and nearby table header cells before falling back to brittle absolute XPath.
