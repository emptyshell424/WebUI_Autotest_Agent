# AI 执行指令文档

> 本文档供 AI 编程助手（Cascade / Copilot / Codex 等）直接执行。
> 每个任务包含：精确文件路径、具体代码改动、运行命令、验证方法。
> AI 应按任务编号顺序执行，每完成一个任务后运行验证命令确认无回归。

---

## 全局约定

- **后端根目录**：`d:\GitHub_repo\00_active\webui-autotest-agent\AutoTest_Backend`
- **前端根目录**：`d:\GitHub_repo\00_active\webui-autotest-agent\AutoTest_Frontend`
- **项目根目录**：`d:\GitHub_repo\00_active\webui-autotest-agent`
- **后端测试命令**：`python AutoTest_Backend/run_backend_tests.py`（cwd = 项目根目录）
- **前端测试命令**：`npm test`（cwd = 前端根目录）
- **前端构建命令**：`npm run build`（cwd = 前端根目录）
- 所有代码改动不得删除已有注释和文档字符串
- 所有 import 语句放在文件顶部
- 改动完成后必须运行对应的验证命令

---

## TASK-01：新建后端日志模块

### 操作

1. **创建文件** `AutoTest_Backend/app/core/logger.py`，内容：

```python
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"autotest.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger
```

2. **在以下 5 个服务文件顶部 import 区域末尾添加**：

```python
from app.core.logger import get_logger

logger = get_logger(__name__)
```

涉及文件（在各文件现有 import 块最后一行之后插入）：

| 文件 | 在哪一行之后插入 |
|------|------------------|
| `app/services/execution_service.py` | 第 14 行 `from app.utils.code_parser import clean_code` 之后 |
| `app/services/generation_service.py` | 第 13 行 `from app.utils.code_parser import clean_code` 之后 |
| `app/services/llm_service.py` | 第 5 行 `from app.services.strategy_service import ...` 之后 |
| `app/services/rag_service.py` | 第 14 行 `chromadb = None` 之后（空行后） |
| `app/services/strategy_service.py` | 第 4 行 `from dataclasses import dataclass` 之后 |

3. **添加关键日志埋点**（以下为必须添加的最小埋点集）：

**`execution_service.py`**：
- `create_execution()` 方法开头添加：`logger.info("Creating execution for test_case_id=%s", test_case_id)`
- `_run_execution()` 中 `try` 块之前添加：`logger.info("Starting execution %s", execution_id)`
- `_execute_script()` 返回结果前添加：`logger.info("Script execution finished: status=%s dir=%s", result.status, run_directory)`（result 变量名根据上下文调整）

**`llm_service.py`**：
- `_complete()` 方法中 `response = client.chat...` 之后添加：`logger.info("LLM response received: model=%s", self.settings.MODEL_NAME)`
- `_complete()` 方法中 `except Exception as exc:` 分支内添加：`logger.exception("LLM request failed")`

**`rag_service.py`**：
- `search()` 方法返回前添加：`logger.info("RAG search: mode=%s query_len=%d results=%d", retrieval_mode, len(query), len(results))` （变量名根据上下文调整）

**`generation_service.py`**：
- `generate()` 方法成功创建 record 后添加：`logger.info("Generated test case id=%s title=%s", record.id, record.title)`

### 验证

```
cd d:\GitHub_repo\00_active\webui-autotest-agent
python AutoTest_Backend/run_backend_tests.py
```

预期：全量通过（≥30/30），无 import 错误。

---

## TASK-02：修复所有 `except Exception: pass`

### 操作

共 2 处，逐一替换：

**位置 1**：`AutoTest_Backend/app/services/execution_service.py`

查找（约第 217-218 行）：
```python
            except Exception:
                pass
```

替换为：
```python
            except Exception:
                logger.exception("Failed to mark execution %s as failed after unexpected error", execution_id)
```

**位置 2**：`AutoTest_Backend/app/services/rag_service.py`

查找（约第 558-559 行）：
```python
        except Exception:
            pass
```

替换为：
```python
        except Exception:
            logger.warning("Failed to delete collection '%s' during reset, continuing", self.collection_name)
```

### 验证

```
cd d:\GitHub_repo\00_active\webui-autotest-agent
python AutoTest_Backend/run_backend_tests.py
```

然后执行全局搜索确认无残留：
```
grep -rn "except Exception:" AutoTest_Backend/app/services/ | grep -i pass
```

预期：grep 无输出（无残留的 except-pass）。

---

## TASK-03：删除残留构建脚本 `run-build.mjs`

### 操作

1. **删除文件**：`AutoTest_Frontend/scripts/run-build.mjs`

2. **确认** `AutoTest_Frontend/package.json` 第 8 行 `"build": "vite build"` 未引用 `run-build.mjs`（当前已是正确状态，无需修改）

3. 检查 `AutoTest_Frontend/scripts/` 目录下是否只剩 `run-tests.mjs`（后续 TASK 可能替换它）

### 验证

```
cd d:\GitHub_repo\00_active\webui-autotest-agent\AutoTest_Frontend
npm run build
```

预期：构建成功，生成 `dist/` 目录。

---

## TASK-04：Settings 页补齐表单标签和组件注册

### 操作

**步骤 1**：在 `AutoTest_Frontend/src/main.js` 中注册 `ElForm` 和 `ElFormItem`。

在 import 块中添加（第 3-22 行 import 列表中）：
```javascript
  ElForm,
  ElFormItem,
```

在 style import 块中添加：
```javascript
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
```

在组件注册数组中添加 `ElForm, ElFormItem`。

**步骤 2**：在 `AutoTest_Frontend/src/i18n/index.js` 中添加标签文案。

在 `en.settings` 对象中（`runtimeHint` 之后）添加：
```javascript
      executionTimeoutLabel: 'Execution timeout (seconds)',
      maxSelfHealLabel: 'Max self-heal attempts',
      maxConcurrentLabel: 'Max concurrent executions',
```

在 `zh-CN.settings` 对象中（`runtimeHint` 之后）添加：
```javascript
      executionTimeoutLabel: '执行超时（秒）',
      maxSelfHealLabel: '最大自愈次数',
      maxConcurrentLabel: '最大并发执行数',
```

**步骤 3**：修改 `AutoTest_Frontend/src/views/SettingsView.vue`。

查找（约第 42-55 行）：
```html
        <div class="settings-form">
          <el-input-number v-model="runtimeDraft.execution_timeout_seconds" :min="1" :max="3600" />
          <el-input-number v-model="runtimeDraft.max_self_heal_attempts" :min="0" :max="10" />
          <el-input-number v-model="runtimeDraft.max_concurrent_executions" :min="1" :max="10" />
```

替换为：
```html
        <div class="settings-form">
          <el-form label-position="top">
            <el-form-item :label="t('settings.executionTimeoutLabel')">
              <el-input-number v-model="runtimeDraft.execution_timeout_seconds" :min="1" :max="3600" />
            </el-form-item>
            <el-form-item :label="t('settings.maxSelfHealLabel')">
              <el-input-number v-model="runtimeDraft.max_self_heal_attempts" :min="0" :max="10" />
            </el-form-item>
            <el-form-item :label="t('settings.maxConcurrentLabel')">
              <el-input-number v-model="runtimeDraft.max_concurrent_executions" :min="1" :max="10" />
            </el-form-item>
          </el-form>
```

### 验证

```
cd d:\GitHub_repo\00_active\webui-autotest-agent\AutoTest_Frontend
npm test
npm run build
```

预期：测试通过，构建成功。启动 `npm run dev` 后 Settings 页每个数字输入框上方有标签文字。

---

## TASK-05：API Client 添加初始 baseURL 和响应拦截器

### 操作

**文件**：`AutoTest_Frontend/src/api/client.js`

当前第 14-16 行：
```javascript
const apiClient = axios.create({
  timeout: 60000,
})
```

替换为：
```javascript
const apiClient = axios.create({
  baseURL: normalizeBaseUrl(
    (typeof window !== 'undefined' && window.localStorage.getItem(STORAGE_KEY)) ||
    DEFAULT_API_BASE_URL
  ),
  timeout: 60000,
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!error.response) {
      error.message = error.message || 'Network error: unable to reach the backend.'
    }
    return Promise.reject(error)
  }
)
```

然后删除文件末尾的第 45 行（现在多余了）：
```javascript
setApiBaseUrl(getStoredApiBaseUrl())
```

### 验证

```
cd d:\GitHub_repo\00_active\webui-autotest-agent\AutoTest_Frontend
npm test
```

预期：测试通过。`apiClient.defaults.baseURL` 在创建时已有值。

---

## TASK-06：后端 API 集成测试

### 操作

**创建文件**：`AutoTest_Backend/tests/test_api_integration.py`，内容：

```python
"""Integration tests exercising the FastAPI endpoints through TestClient."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the backend package is importable
_backend_root = Path(__file__).resolve().parents[1]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from tests.runtime_support import TEST_RUNTIME_ROOT_ENV


def _make_settings(**overrides):
    tmp = tempfile.mkdtemp(prefix="api_int_")
    os.environ[TEST_RUNTIME_ROOT_ENV] = tmp
    from app.core.config import Settings

    defaults = dict(
        SQLITE_DB_PATH=str(Path(tmp) / "test.db"),
        VECTOR_STORE_DIR=str(Path(tmp) / "rag"),
        KNOWLEDGE_BASE_DIR=str(Path(tmp) / "knowledge"),
        EXECUTIONS_DIR=str(Path(tmp) / "runs"),
        DEEPSEEK_API_KEY="test-key",
    )
    defaults.update(overrides)
    return Settings(**defaults)


class TestHealthEndpointIntegration(unittest.TestCase):
    def setUp(self):
        settings = _make_settings()
        from app.main import create_app

        self.app = create_app(settings)
        from app.core.container import create_container

        self.app.state.container = create_container(settings)
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            from starlette.testclient import TestClient
        self.client = TestClient(self.app)

    def test_health_returns_200(self):
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("status", body)
        self.assertIn("backend", body)

    def test_settings_get_returns_200(self):
        resp = self.client.get("/api/v1/settings")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("settings", body)
        self.assertIsInstance(body["settings"]["execution_timeout_seconds"], int)

    def test_settings_put_updates_value(self):
        payload = {
            "execution_timeout_seconds": 120,
            "max_self_heal_attempts": 2,
            "max_concurrent_executions": 3,
        }
        resp = self.client.put("/api/v1/settings", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["settings"]["execution_timeout_seconds"], 120)
        self.assertEqual(body["settings"]["max_self_heal_attempts"], 2)

    def test_executions_list_returns_200(self):
        resp = self.client.get("/api/v1/executions", params={"limit": 5})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("items", body)
        self.assertIsInstance(body["items"], list)

    def test_executions_stats_returns_200(self):
        resp = self.client.get("/api/v1/executions/stats")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("metrics", body)

    def test_generate_with_mock_llm(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "```python\nfrom selenium import webdriver\ndriver = webdriver.Chrome()\n"
            "driver.get('https://www.baidu.com')\nprint('Test Completed')\ndriver.quit()\n```"
        )
        with patch("app.services.llm_service.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            MockOpenAI.return_value = mock_client
            resp = self.client.post(
                "/api/v1/generate",
                json={"prompt": "打开百度首页并打印测试完成", "retrieval_mode": "vector"},
            )
        self.assertIn(resp.status_code, (200, 201))
        body = resp.json()
        self.assertIn("case", body)
        self.assertIn("id", body["case"])

    def test_create_execution_requires_test_case(self):
        resp = self.client.post(
            "/api/v1/executions",
            json={"test_case_id": "nonexistent-id"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_cancel_nonexistent_execution(self):
        resp = self.client.delete("/api/v1/executions/nonexistent-id")
        self.assertIn(resp.status_code, (404, 409))


if __name__ == "__main__":
    unittest.main()
```

### 验证

```
cd d:\GitHub_repo\00_active\webui-autotest-agent
python AutoTest_Backend/run_backend_tests.py
```

预期：总用例数 ≥38（原 30 + 新 8），全部通过。

---

## TASK-07：扩充知识库文档（6 份）

### 操作

在 `AutoTest_Backend/docs/knowledge/` 下创建以下 6 个文件。每个文件遵循现有格式：以 `Keywords:` 开头，包含场景描述和 Selenium 代码示例。

**文件 1**：`file_upload_patterns.md`

```markdown
Keywords: file upload, input type file, 文件上传, 上传文件, attach file, browse file

## File Upload Patterns

### Standard file input
Use `send_keys()` on the hidden file input element to attach a file without opening a native dialog.

```python
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

file_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
file_input.send_keys("/absolute/path/to/test-file.txt")
```

### Common pitfalls
- Never use `click()` on a file input — it opens a native OS dialog that Selenium cannot control.
- If the file input is hidden, use JavaScript to make it visible first:
  `driver.execute_script("arguments[0].style.display = 'block';", file_input)`
- Always use absolute paths for file attachments.
```

**文件 2**：`select_dropdown_patterns.md`

```markdown
Keywords: select, dropdown, 下拉选择, 下拉框, option, cascader, el-select

## Select / Dropdown Patterns

### Native HTML select
```python
from selenium.webdriver.support.ui import Select

select_el = Select(driver.find_element(By.ID, "mySelect"))
select_el.select_by_visible_text("Option Text")
```

### Element Plus el-select
Element Plus renders a custom dropdown, not a native `<select>`. Steps:
1. Click the `.el-select` trigger to open the dropdown.
2. Wait for `.el-select-dropdown__item` to become visible.
3. Click the desired option by its text content.

```python
trigger = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, ".el-select .el-input"))
)
trigger.click()
option = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//li[contains(@class,'el-select-dropdown__item') and contains(.,'Target Text')]"))
)
option.click()
```

### Common pitfalls
- Element Plus dropdowns often render in a teleported container at `<body>` level, not inside the form.
- Use XPath text matching rather than CSS selectors for option selection.
```

**文件 3**：`tab_switch_patterns.md`

```markdown
Keywords: tab, tabs, 标签页, 切换标签, el-tabs, tab switch, tab panel

## Tab Switch Patterns

### Element Plus el-tabs
```python
tab = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'el-tabs__item') and contains(.,'Tab Label')]"))
)
tab.click()

# Wait for the tab panel content to load
WebDriverWait(driver, 10).until(
    EC.visibility_of_element_located((By.CSS_SELECTOR, ".el-tab-pane.is-active"))
)
```

### Browser tabs (windows)
```python
# Open new tab
driver.execute_script("window.open('https://example.com', '_blank');")
# Switch to new tab
driver.switch_to.window(driver.window_handles[-1])
# Switch back
driver.switch_to.window(driver.window_handles[0])
```

### Common pitfalls
- Element Plus tabs use `role="tab"` and `aria-selected` attributes — prefer these for stable selectors.
- After switching browser tabs, always explicitly wait for page content in the new tab.
```

**文件 4**：`hover_menu_patterns.md`

```markdown
Keywords: hover, menu, tooltip, dropdown menu, 鼠标悬停, 悬浮菜单, popover, submenu

## Hover Menu / Tooltip Patterns

### ActionChains hover
```python
from selenium.webdriver.common.action_chains import ActionChains

menu_trigger = WebDriverWait(driver, 10).until(
    EC.visibility_of_element_located((By.CSS_SELECTOR, ".nav-menu-item"))
)
ActionChains(driver).move_to_element(menu_trigger).perform()

submenu_item = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, ".submenu-item"))
)
submenu_item.click()
```

### Common pitfalls
- Hover-triggered menus may disappear if the mouse moves away before clicking — chain the hover and click together or add a short wait.
- Element Plus `el-dropdown` uses `trigger="hover"` by default; the dropdown panel appears in a teleported container at `<body>`.
- Prefer `ActionChains.move_to_element()` over JavaScript `dispatchEvent('mouseenter')`.
```

**文件 5**：`drag_sort_patterns.md`

```markdown
Keywords: drag, drop, sort, sortable, 拖拽, 排序, drag and drop, reorder

## Drag and Drop / Sortable Patterns

### ActionChains drag_and_drop
```python
from selenium.webdriver.common.action_chains import ActionChains

source = driver.find_element(By.CSS_SELECTOR, ".sortable-item:nth-child(1)")
target = driver.find_element(By.CSS_SELECTOR, ".sortable-item:nth-child(3)")
ActionChains(driver).drag_and_drop(source, target).perform()
```

### Manual click-hold-move-release (more reliable for JS libraries)
```python
ActionChains(driver)\
    .click_and_hold(source)\
    .pause(0.5)\
    .move_to_element(target)\
    .pause(0.5)\
    .release()\
    .perform()
```

### Common pitfalls
- Many JS sortable libraries (SortableJS, Vue.Draggable) intercept native drag events — the manual hold-move-release approach is more reliable.
- Add `pause()` between steps to allow the library to register the drag state.
- After drop, verify the new order by re-querying the element list.
```

**文件 6**：`table_pagination_patterns.md`

```markdown
Keywords: table, pagination, 表格分页, 翻页, next page, page size, sort column, 排序

## Table Pagination & Sorting Patterns

### Element Plus el-pagination — click next page
```python
next_btn = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, ".el-pagination .btn-next"))
)
next_btn.click()

# Wait for table data to refresh
WebDriverWait(driver, 10).until(
    EC.staleness_of(driver.find_element(By.CSS_SELECTOR, ".el-table__body tr:first-child"))
)
```

### Click a column header to sort
```python
header = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//th[contains(.,'Column Name')]"))
)
header.click()

# Verify sort indicator
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "th.ascending, th.descending"))
)
```

### Common pitfalls
- After pagination or sort, table rows are re-rendered — old element references become stale. Always re-query.
- Use `staleness_of` or explicit content checks rather than `time.sleep()`.
- Element Plus pagination renders page number buttons as `<li>` inside `.el-pager`.
```

### 验证

确认 `AutoTest_Backend/docs/knowledge/` 目录下有 ≥18 个 `.md` 文件：
```
dir AutoTest_Backend\docs\knowledge\*.md
```

---

## TASK-08：根目录 README

### 操作

**创建文件**：`README.md`（项目根目录）

```markdown
# WebUI AutoTest Agent

An intelligent Web UI test automation platform: **natural language → RAG-enhanced retrieval → Selenium script generation → local execution → failure self-healing → result statistics**.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3, Vite, Element Plus, Pinia, Vue Router |
| Backend | FastAPI, Pydantic Settings, SQLite, Selenium |
| LLM | DeepSeek (via OpenAI SDK) |
| RAG | ChromaDB (vector) + BM25 (keyword) + rerank |
| CI | GitHub Actions |

## Quick Start

### Prerequisites

- Python ≥ 3.12
- Node.js ≥ 24
- Chrome browser + ChromeDriver in PATH

### Backend

```bash
cd AutoTest_Backend
cp .env.example .env          # fill in DEEPSEEK_API_KEY
pip install -r requirements.txt
python -m app.main             # starts at http://127.0.0.1:8000
```

### Frontend

```bash
cd AutoTest_Frontend
npm install
npm run dev                    # starts at http://localhost:5173
```

### Run Tests

```bash
# Backend (from project root)
python AutoTest_Backend/run_backend_tests.py

# Frontend
cd AutoTest_Frontend && npm test
```

## Project Structure

```
├── AutoTest_Backend/       # FastAPI backend
│   ├── app/
│   │   ├── api/            # Route handlers
│   │   ├── core/           # Config, database, exceptions, logger
│   │   ├── models/         # Data entities
│   │   ├── repositories/   # SQLite data access
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Business logic
│   │   └── utils/          # Code parser utilities
│   ├── docs/knowledge/     # RAG knowledge base documents
│   └── tests/              # Backend test suite
├── AutoTest_Frontend/      # Vue 3 frontend
│   └── src/
│       ├── api/            # Axios client
│       ├── i18n/           # Internationalization (EN / zh-CN)
│       ├── stores/         # Pinia stores
│       ├── view-models/    # Pure logic helpers
│       └── views/          # Page components
├── vue-admin-template/     # Local test target (reference only)
├── docs/                   # Project documentation
└── .github/workflows/      # CI configuration
```

## Documentation

- [Project Summary](docs/PROJECT_SUMMARY.md)
- [Project Plan](docs/PROJECT_PLAN.md)
- [Development Status](docs/DEVELOPMENT_STATUS_NEXT_STEPS.md)
- [Issues Audit](docs/PROJECT_ISSUES_AUDIT.md)
- [Optimization Audit](docs/OPTIMIZATION_AUDIT.md)
- [Execution Plan](docs/EXECUTION_PLAN.md)
- [Unfinished Tasks](docs/UNFINISHED_TASKS.md)
- [Technical Documentation](docs/PROJECT_TECHNICAL_DOCUMENTATION.md)
- [Experiment Results Template](docs/TASK_SPEC_EXPERIMENT_RESULTS.md)
```

### 验证

确认文件存在：`dir README.md`

---

## 执行顺序与依赖关系

```
TASK-01 (日志模块)
    ↓
TASK-02 (修复 except-pass，依赖 TASK-01 的 logger)
    ↓
TASK-03 (删除 run-build.mjs，独立)
TASK-04 (Settings 表单标签，独立)
TASK-05 (API Client 拦截器，独立)
    ↓  ← TASK-03/04/05 可并行
TASK-06 (后端集成测试，依赖 TASK-01/02 已完成)
TASK-07 (知识库文档，独立)
TASK-08 (根目录 README，独立)
    ↓  ← TASK-06/07/08 可并行
全部完成
```

## 每个 TASK 完成后的检查清单

| 检查项 | 命令 |
|--------|------|
| 后端测试通过 | `python AutoTest_Backend/run_backend_tests.py` |
| 前端测试通过 | `cd AutoTest_Frontend && npm test` |
| 前端构建通过 | `cd AutoTest_Frontend && npm run build` |
| 无 except-pass 残留 | `grep -rn "except Exception" AutoTest_Backend/app/services/ \| grep pass` |

## 执行完毕后的总验收

1. 后端测试 ≥38 个用例全部通过
2. 前端测试全部通过
3. 前端构建成功
4. 知识库 ≥18 份文档
5. 后端启动后控制台有结构化日志
6. Settings 页有表单标签
7. 根目录有 README.md
