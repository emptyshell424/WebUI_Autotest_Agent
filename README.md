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

## 系统结构

```text
WebUI_Autotest_Agent
├─ AutoTest_Backend
│  ├─ app
│  ├─ docs
│  ├─ tests
│  ├─ .env.example
│  ├─ pyproject.toml
│  ├─ requirements.txt
│  └─ run_backend_tests.py
├─ AutoTest_Frontend
│  ├─ src
│  ├─ .env.example
│  ├─ package.json
│  └─ README.md
└─ vue-admin-template
```

## 一次性准备

### 1. 后端环境

```powershell
cd .\AutoTest_Backend\
copy .env.example .env
uv venv
.\.venv\Scripts\activate
uv sync
```

如果你没有安装 `uv`，先执行：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

后端 `.env` 至少需要确认这些变量：

```env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-chat
```

说明：

- 未配置 `DEEPSEEK_API_KEY` 时，健康检查可用，但脚本生成和自愈不会正常工作。
- `data/`、`runs/` 都是运行期目录，不应提交到仓库。

### 2. 前端环境

```powershell
cd .\AutoTest_Frontend\
copy .env.example .env
npm install
```

默认前端环境变量：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## 启动步骤

### 启动后端

```powershell
cd .\AutoTest_Backend\
.\.venv\Scripts\activate
python -m app.main
```

默认地址：`http://127.0.0.1:8000`

### 启动前端

新开一个终端窗口：

```powershell
cd .\AutoTest_Frontend\
npm run dev
```

默认地址：`http://127.0.0.1:5173`

## 最小验证流程

1. 打开前端 `http://127.0.0.1:5173`
2. 进入 `Settings` 页面刷新健康状态
3. 先执行一次知识库重建
4. 回到 `Workbench` 输入一个简单场景并生成脚本
5. 运行脚本，去 `History` 和 `Metrics` 页面确认记录和统计是否更新

## 测试与验证

### 后端测试

统一入口：

```powershell
python .\AutoTest_Backend\run_backend_tests.py
```

这个入口会自动处理测试发现路径，避免因为当前工作目录不同导致 `app` 模块导入失败。

### 前端构建检查

```powershell
cd .\AutoTest_Frontend\
npm run build
```

## 知识库与实验素材

- 知识库目录：[AutoTest_Backend/docs/knowledge](D:\GitHub_repo\WebUI_Autotest_Agent\AutoTest_Backend\docs\knowledge)
- 实验场景建议：[AutoTest_Backend/docs/EXPERIMENT_SCENARIOS.md](D:\GitHub_repo\WebUI_Autotest_Agent\AutoTest_Backend\docs\EXPERIMENT_SCENARIOS.md)

## 当前完成度判断

当前仓库已经完成以下可演示能力：

- 自然语言生成 Selenium Python 脚本
- 基于本地知识库的 RAG 检索增强
- 本地执行脚本、记录 stdout/stderr 与执行状态
- 首次执行失败后触发一轮自动修复
- 查看执行历史、自愈记录、修复代码与统计指标

当前仍需继续打磨的重点：

- 增加更多真实站点或本地靶场场景的实验数据
- 扩充测试覆盖，尤其是 API 集成测试和前端交互验证
- 补充答辩用实验数据、截图和故障案例对比

## 注意事项

- `AutoTest_Backend/.env` 和 `AutoTest_Frontend/.env` 属于本地私有配置，不应提交。
- `AutoTest_Backend/data/`、`AutoTest_Backend/runs/`、向量索引和 SQLite 文件属于运行产物，不应提交。
- `vue-admin-template` 目录可作为本地参考靶场，但不属于主系统运行主线。
