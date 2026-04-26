# Element UI Form and Table Patterns / Element UI 表单与表格模式

Keywords: element ui, form, table, 表单, 表格, el-table, el-table__header, loading, Activity name, Activity zone, Create, message, Title, Author, Pageviews, Status.

For Element UI forms and tables, prefer stable labels, visible button text, and persistent containers. Verify submit outcomes with a visible message, stable table row, or a clear page-state change.

对于 Element UI 表格，应先等待 `.el-table` 可见，再等待 loading mask 消失或至少一行表格数据出现。验证列时优先读取 `.el-table__header` 或 header cell 文本，确认目标列名存在，而不是依赖固定列序号。

For vue-admin-template Example/Table, expected visible columns include `Title`, `Author`, `Pageviews`, and `Status`. A reliable table assertion checks both headers and at least one rendered row.
