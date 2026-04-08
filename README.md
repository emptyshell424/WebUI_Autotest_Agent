# AutoTest Agent

AutoTest Agent 是一个面向毕业设计场景的 Web UI 自动化测试平台。系统支持将自然语言测试需求转换为 Selenium Python 脚本，在本地执行脚本，并在首次执行失败后尝试基于错误日志进行一次自动修复与重试。

这个项目同时服务两个目标：

1. 毕业设计答辩：形成“脚本生成 -> 执行 -> 失败诊断 -> 自愈重试 -> 结果统计”的完整技术闭环。
2. 求职作品集：展示你在后端设计、前后端联调、AI 应用落地、自动化测试平台和工程化实现方面的能力。

## 项目亮点

- 自然语言生成 Selenium UI 自动化脚本
- 基于本地知识库的 RAG 增强生成
- 本地执行测试脚本并记录日志、错误和历史记录
- 首次执行失败后自动触发一轮脚本修复
- 展示修复摘要、修复后代码和最终结果
- 统计首次成功率、自愈触发率、自愈成功率和最终成功率

## 技术栈

### 前端

- Vue 3
- Vite
- Element Plus
- Pinia
- Vue Router

### 后端

- FastAPI
- OpenAI-compatible SDK
- ChromaDB
- SQLite
- Selenium

### 运行模式

- 本地后端服务
- 本地浏览器执行 Selenium 脚本
- 本地知识库与运行记录持久化

## 系统结构

```text
Graduation_Project
├─ AutoTest_Backend
│  ├─ app
│  │  ├─ api            # 接口层
│  │  ├─ core           # 配置、容器、数据库初始化、异常
│  │  ├─ models         # 数据实体
│  │  ├─ repositories   # 数据访问层
│  │  ├─ schemas        # API 请求/响应模型
│  │  ├─ services       # 生成、执行、自愈、RAG 等核心逻辑
│  │  └─ utils          # 代码清洗等工具
│  ├─ docs
│  │  ├─ knowledge      # RAG 知识库素材
│  │  └─ EXPERIMENT_SCENARIOS.md
│  ├─ data              # SQLite 和 Chroma 运行数据
│  ├─ runs              # 每次执行的脚本与日志目录
│  ├─ tests             # 后端测试
│  ├─ pyproject.toml    # uv 项目配置
│  └─ requirements.txt  # 兼容保留
├─ AutoTest_Frontend
│  ├─ src
│  │  ├─ api
│  │  ├─ router
│  │  ├─ stores
│  │  └─ views
│  └─ package.json
└─ vue-admin-template   # 本地参考靶场
```

## 核心流程

### 1. 脚本生成

用户在前端输入自然语言测试需求，例如：

> 打开百度首页，在搜索框输入 DeepSeek，提交搜索，并验证结果页出现相关内容。

后端会：

1. 对需求进行基础校验
2. 从本地知识库中检索相关 Selenium 知识片段
3. 将需求和知识上下文一起发送给大模型
4. 返回生成后的 Selenium Python 脚本
5. 将测试用例与原始生成结果保存到 SQLite

### 2. 脚本执行

用户可以直接运行生成后的脚本。后端会：

1. 对脚本做 AST 安全校验
2. 为本次执行创建独立运行目录
3. 写入 `generated_test.py`
4. 调用 Python 子进程执行
5. 保存 `stdout.log`、`stderr.log` 和执行状态

### 3. 自愈重试

如果首次执行失败，系统会自动进入一次轻量自愈流程：

1. 收集原始需求、原始脚本、RAG 上下文、标准输出和报错信息
2. 调用大模型生成修复后的脚本
3. 对修复后的脚本再次做安全校验
4. 自动执行修复后的脚本
5. 保存修复尝试记录、修复摘要和修复后的代码

当前自愈设计为：

- 最多 1 次自动修复重试
- 不引入重型 LangChain 或多 Agent 编排
- 优先保证毕业设计场景下的可解释性和可落地性

## 前端页面说明

### Workbench

工作台用于：

- 输入自然语言测试需求
- 生成 Selenium 脚本
- 手动修改脚本
- 执行当前脚本
- 查看执行日志
- 查看修复尝试时间线

### History

历史页用于：

- 查看最近执行记录
- 区分首次成功、自愈成功、自愈失败和安全阻断
- 查看每次执行的脚本、日志和修复代码

### Metrics

指标页用于：

- 展示生成数量和执行数量
- 展示首次成功率
- 展示自愈触发率
- 展示自愈成功率
- 展示最终成功率

### Settings

设置页用于：

- 配置后端 API 地址
- 查看系统健康状态
- 重建知识库

## API 概览

### 健康检查

- `GET /api/v1/health`

返回后端、模型、知识库和本地存储的健康状态。

### 脚本生成

- `POST /api/v1/generate`

请求示例：

```json
{
  "prompt": "Open the login page, enter credentials, submit, and verify the dashboard welcome message."
}
```

### 创建执行

- `POST /api/v1/executions`

请求示例：

```json
{
  "test_case_id": "uuid",
  "code_override": null
}
```

### 查询执行列表

- `GET /api/v1/executions`

返回最近执行记录，包含是否触发自愈和修复次数。

### 查询单次执行详情

- `GET /api/v1/executions/{id}`

返回执行详情，包括：

- 原始执行结果
- 安全校验错误
- 修复尝试记录
- 修复说明
- 修复后代码

### 查询指标

- `GET /api/v1/executions/stats`

返回聚合后的实验指标。

### 重建知识库

- `POST /api/v1/knowledge/rebuild`

重建 Chroma 向量索引。

## 本地启动

### 后端启动方式：使用 uv

进入后端目录：

```powershell
cd .\AutoTest_Backend\
```

如果本机还没安装 `uv`，先安装：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

然后初始化环境并安装依赖：

```powershell
copy .env.example .env
uv venv
.\.venv\Scripts\activate
uv sync
```

启动后端：

```powershell
python -m app.main
```

默认地址：

- 后端：`http://127.0.0.1:8000`

### 前端启动

进入前端目录：

```powershell
cd .\AutoTest_Frontend\
copy .env.example .env
npm install
npm run dev
```

默认地址：

- 前端：`http://127.0.0.1:5173`

## 环境配置

后端 `.env` 至少需要配置：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-chat
```

说明：

- `DEEPSEEK_API_KEY` 未配置时，脚本生成和自愈功能无法正常调用模型
- 知识库和 SQLite 数据会自动初始化到本地目录

## 知识库与实验素材

### 知识库目录

位于：

- [AutoTest_Backend/docs/knowledge](D:\GitHub_repo\Graduation_Project\AutoTest_Backend\docs\knowledge)

目前覆盖内容包括：

- Selenium 显式等待
- 定位策略
- 动态页面处理
- iframe / 新窗口 / 弹窗
- 常见失败模式
- 典型 Web 测试模式

### 实验场景建议

位于：

- [AutoTest_Backend/docs/EXPERIMENT_SCENARIOS.md](D:\GitHub_repo\Graduation_Project\AutoTest_Backend\docs\EXPERIMENT_SCENARIOS.md)

适合用于：

- 中期答辩和最终答辩演示
- 论文实验设计
- 首次成功率和自愈成功率统计

## 测试与验证

### 后端测试

```powershell
cd .\AutoTest_Backend\
.\.venv\Scripts\python -m unittest discover -s tests
```

### 前端构建检查

```powershell
cd .\AutoTest_Frontend\
npm run build
```

## 推荐演示流程

1. 在 Settings 页面刷新系统健康状态
2. 重建知识库
3. 在 Workbench 输入一个简单测试场景
4. 生成脚本并执行
5. 展示首次成功案例
6. 再展示一个失败后自动修复的案例
7. 去 History 页面查看修复前后记录
8. 去 Metrics 页面展示统计指标

## 项目当前定位

这个项目不是一个通用测试框架，而是一个面向“AI + 测试开发”场景的研究型原型系统。它的目标不是完全替代测试开发工程师，而是验证：

- 大模型是否能降低 UI 自动化脚本编写成本
- 自愈机制是否能降低脚本维护成本
- 如何把脚本生成、执行、修复和统计整合成一个测试平台

## 后续可扩展方向

- 支持多轮自愈而不是单轮自愈
- 引入更丰富的页面上下文，例如 DOM 摘要或截图分析
- 支持更复杂的实验报告与图表
- 接入持续集成流程
- 支持更多测试框架，例如 Playwright

## 注意事项

- 运行数据目录如 `data/`、`runs/`、向量索引等已加入忽略规则
- 当前自愈是轻量实现，强调可解释性和工程可控性
- `vue-admin-template` 目录可作为本地参考靶场，但不属于主系统运行主线
