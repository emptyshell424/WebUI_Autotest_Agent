# AutoTest Frontend

这是 `AutoTest Agent` 的前端界面，负责脚本生成、执行历史、自愈记录、指标统计和系统设置展示。

## 技术栈

- Vue 3
- Vite
- Element Plus
- Pinia
- Vue Router

## 页面说明

- `Workbench`：输入自然语言测试需求，生成并执行 Selenium 脚本
- `History`：查看执行历史、日志、自愈尝试和修复后代码
- `Metrics`：查看生成量、执行量和成功率指标
- `Settings`：查看健康状态、配置后端 API、重建知识库

## 一次性准备

```powershell
cd .\AutoTest_Frontend\
copy .env.example .env
npm install
```

默认环境变量：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## 启动

```powershell
cd .\AutoTest_Frontend\
npm run dev
```

默认开发地址：

- `http://127.0.0.1:5173`

## 构建

```powershell
cd .\AutoTest_Frontend\
npm run build
```

## 说明

- `AutoTest_Frontend/.env` 属于本地配置，不应提交到仓库。
- 如果后端地址变化，只需修改 `VITE_API_BASE_URL`。
