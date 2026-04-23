# 本项目未完成任务梳理

更新时间：2026-04-22（P0 已完成，P1 已新增前端测试入口与 CI，部分 P1/P2 能力已落地）

## 结论

这个项目的核心闭环已经存在：

`自然语言需求 -> RAG 检索增强 -> Selenium 脚本生成 -> 本地执行 -> 失败后自愈 -> 历史记录与指标展示`

所以当前真正未完成的部分，不是“主流程完全没做”，而是下面三类：

1. 自动化验证还不够稳定，导致“做出来了”和“可重复证明能跑”之间有断层。
2. 答辩/演示资料还不完整，缺少可复现的实验结果沉淀。
3. 工程化能力还停留在单机演示级，距离更稳的项目形态还有差距。

## 本轮已完成

- 已完成 `P0-修复后端测试可运行性`。
- 后端测试运行时目录不再写死到 `AutoTest_Backend/tests/_*runtime`，改为由 `AutoTest_Backend/tests/runtime_support.py` 统一管理的受控临时目录。
- `AutoTest_Backend/run_backend_tests.py` 现在会显式初始化测试运行时根目录，避免测试各自散落创建临时路径。
- 同时修正了 `RAGService` 的文档分块策略：`Keywords:` 不再被单独切成高噪声 chunk，避免 rerank 选中关键词块而丢掉正文信息。
- 已验证：执行 `python AutoTest_Backend/run_backend_tests.py`，`30/30` 测试通过。
- 已完成 `P0-实验结果沉淀` 的文档化基础版本：
  - 新增正式实验记录：`AutoTest_Backend/docs/EXPERIMENT_RESULTS.md`
  - 新增任务规格：`docs/TASK_SPEC_EXPERIMENT_RESULTS.md`
  - 已把“已验证事实”和“待执行手工实验”明确拆开，避免把场景建议伪装成实验结果。
- 已新增前端自动化测试入口：`AutoTest_Frontend/npm test`
  - 当前覆盖 `api client`、`app/workspace stores` 以及 `Workbench / History / Metrics` 的关键纯逻辑 helper。
- 已接入最小 CI：`.github/workflows/ci.yml`
  - 后端跑 `python AutoTest_Backend/run_backend_tests.py`
  - 前端跑 `npm test` 和 `npm run build`
- 当前机器上的一个已知环境阻塞：
  - 本地执行 `npm run build` 仍会因为 Vite/Node 在 Windows 下触发 `spawn EPERM` 而失败。
  - 这个问题当前表现为本机验证环境限制，不是后端测试回归，也不是前端业务断言失败。
- 已落地一部分 `P1/P2` 能力：
  - 新增运行时设置 API：`GET/PUT /api/v1/settings`
  - 支持执行历史分页总数与状态筛选
  - 指标返回最近 7 个批次桶的趋势数据
  - 执行编排增加启动时中断任务恢复与并发上限控制

## 本次梳理依据

我这次不是只看 README，而是结合仓库和实际检查结果做判断：

- `README.md` 已明确写出核心能力已完成，同时也写了“仍需继续打磨”的方向。
- `AutoTest_Frontend` 在本地执行 `npm run build` 通过，说明前端当前可以构建。
- `AutoTest_Backend` 执行 `python AutoTest_Backend/run_backend_tests.py` 时，共跑了 30 个测试，其中 14 个通过，16 个报错。
- 这 16 个报错不是功能断言失败，而是测试运行时目录创建失败，集中出现在：
  - `AutoTest_Backend/tests/test_database_migrations.py`
  - `AutoTest_Backend/tests/test_health_endpoint.py`
  - `AutoTest_Backend/tests/test_rag_service.py`
  - `AutoTest_Backend/tests/test_self_heal_flow.py`
- `AutoTest_Frontend/package.json` 只有 `dev / build / preview`，没有测试或 lint 脚本。
- 仓库里没有 `.github/workflows`，说明 CI 没接上。
- `AutoTest_Backend/docs/knowledge` 当前只有 12 份知识文档。
- `AutoTest_Backend/docs/EXPERIMENT_SCENARIOS.md` 只有实验场景建议，没有实验结果、截图、对比表或结论沉淀。
- `README.md` 已明确说明 `vue-admin-template` 只是本地参考靶场，不属于主系统运行主线。

## 未完成任务清单

| 优先级 | 任务 | 当前事实 | 完成标准 |
| --- | --- | --- | --- |
| P0 | 修复后端测试可运行性 | 已完成。测试运行时目录已改为受控临时目录；原先 16 个 `PermissionError` 已消失；`RAGService` 因 chunk 切分导致的 1 个真实失败也已修复。 | 已达成：`python AutoTest_Backend/run_backend_tests.py` 全量 `30/30` 通过。 |
| P0 | 补齐答辩级实验结果沉淀 | 已完成文档骨架和首版基线结果沉淀：已有正式实验记录文件、批次摘要、结果表、证据字段和待补证据清单。当前缺的不是结构，而是后续手工批次的真实截图和运行记录。 | 已部分达成：正式实验记录已落地。剩余工作是执行手工实验批次并补齐截图、历史记录 id、首轮失败/自愈后成功的对比证据。 |
| P1 | 给前端补自动化测试 | 已新增统一命令 `npm test`，当前先覆盖 store 和页面纯逻辑层。浏览器级组件测试 / E2E 仍未完成，根因是当前本地环境对 Node 子进程 / 依赖安装存在 `EPERM` 限制。 | 已部分达成：统一测试命令已存在并可运行。剩余工作是补 `Settings` 页与浏览器级交互测试。 |
| P1 | 接入 CI | 已完成最小版本，仓库新增 `.github/workflows/ci.yml`。 | 已达成：PR / push 自动执行后端测试、前端测试、前端构建。 |
| P1 | 扩充知识库和稳定靶场覆盖 | 当前知识库只有 12 份模式文档，且 README 已承认还需要补真实站点或本地靶场实验数据；`vue-admin-template` 目前也只是参考，不是完整主线。 | 形成更稳定的靶场来源，并补充更多高频场景知识文档，至少覆盖登录、搜索、表单、表格、iframe、弹窗、异步加载等核心流。 |
| P1 | 提升执行编排稳定性 | 已完成一部分：应用启动时会把遗留 `queued/running` 任务恢复为失败，并支持并发上限控制；但仍然是进程内线程模型，尚不支持真正取消和跨进程队列。 | 已部分达成：重启后一致性和并发上限已补上。剩余工作是取消能力和更稳的任务编排模型。 |
| P2 | 开放系统运行参数配置 | 已完成后端 API 和前端界面基础版：可查看/修改 `execution_timeout_seconds`、`max_self_heal_attempts`、`max_concurrent_executions`。 | 已达成基础版。剩余工作是补更完整的参数集和更细的校验反馈。 |
| P2 | 增强历史与指标分析能力 | 已完成基础版：历史支持状态筛选和总数分页，指标支持趋势桶。尚未支持导出与更细实验维度分析。 | 已部分达成：分页/筛选/趋势已具备。剩余工作是导出和更细实验批次维度。 |
| P2 | 整理项目文档体系 | 现在 README 负责项目说明，`docs` 下只有模板，没有正式 backlog、迭代计划、实验记录和验收标准文档体系。 | 形成最基本的文档结构：项目待办、实验记录、任务规格、验收清单。 |

## 推荐执行顺序

建议不要平均发力，顺序应该是：

1. 先补 `P1-知识库/靶场覆盖`。现在验证基线、CI、实验记录骨架都已有，下一瓶颈是场景覆盖和真实实验数据。
2. 再继续深化 `P1-执行编排稳定性`，特别是取消能力和更稳的后台任务模型。
3. 然后再扩展 `P2` 中尚未完成的导出、实验维度分析和更多运行参数。

## 不应该误判为“未完成”的部分

下面这些内容不该再被当成“完全没做”：

- 前后端基本联通已经存在。
- 脚本生成、自愈、历史、指标四条主线已经落地。
- 前端构建当前是通过的。
- 后端并不是没有测试，而是测试稳定性和可运行性还没收口。

## 可以直接拆成任务的下一步

如果你要继续推进，我建议下一轮直接拆成下面 4 个实现任务：

1. 用正式实验记录模板补首批手工实验结果和截图。
2. 扩充知识库与靶场覆盖，优先登录、搜索、表单、表格、iframe、弹窗、异步加载。
3. 深化执行编排，补取消能力和更稳的后台任务模型。
4. 继续补前端浏览器级交互测试，替换当前只覆盖逻辑层的测试边界。
