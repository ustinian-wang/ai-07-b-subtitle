# ai-07-b-subtitle

**多平台笔记提取与管理**：粘贴 B 站 / 小红书链接 → 本地笔记库 → 对话分析 / 同步 Notion。

> 目录名保留 `b-subtitle` 历史命名；API 前缀仍为 `/api/v1/subtitle`。本仓库为 **独立 Git 项目**，可单独 clone / push。

## 5 分钟上手

### 环境要求

- **Python ≥ 3.10**、**Node.js ≥ 18**
- 可选：**pm2**（推荐，一键启停 + 热更）

### 1. 启动

```bash
# 在项目根目录执行

# 方式 A：pm2（推荐）
pm2 start ecosystem.config.cjs

# 方式 B：手动
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8907 --reload --reload-dir app
# 新终端
cd frontend && npm install && npm run dev -- --host 0.0.0.0 --port 9177
```

### 2. 打开页面

| 地址 | 说明 |
|------|------|
| http://localhost:9177 | 前端（笔记库 + 提取 + 对话） |
| http://localhost:8907/api/health | 后端健康检查 |

### 3. 第一次提取

1. 在中间输入框粘贴 B 站 BV 链接或小红书链接
2. 点 **提取** → 成功后自动保存到左侧笔记库
3. 点击侧栏笔记可查看全文；右侧可开对话（需先配 LLM，见下）

```bash
curl http://localhost:8907/api/health
# {"ok":true,"project":"ai-07-b-subtitle",...}
```

## 按需配置（不必一次配齐）

进入左下角 **设置**，按你需要的能力逐项填写：

| 你想用… | 要配什么 | 不配会怎样 |
|---------|----------|------------|
| B 站需登录字幕 | `SESSDATA` | 部分视频提示需登录 |
| 小红书笔记 | 小红书 Cookie | 抓取失败 |
| 右侧对话助手 | OpenAI API Key + Base URL + Model | 对话不可用 |
| 同步 Notion | Integration Token + 父页面 ID | 「同步 Notion」报未配置 |

配置写入 `backend/data/settings.json`（不入 Git）。也可用 `backend/.env` 作 fallback，见 [配置说明](docs/configuration.md)。

## 常见使用场景

| 场景 | 怎么做 | 详情 |
|------|--------|------|
| 网页粘贴链接提取 | 首页输入 URL → 提取 | [使用指南 · 提取笔记](docs/user-guide.md#提取笔记) |
| 管理文件夹 / 批量导出 | 左侧笔记库 | [使用指南 · 笔记库](docs/user-guide.md#笔记库) |
| @ 引用笔记对话 | 右侧对话区输入 `@` 或拖拽笔记 | [使用指南 · 对话助手](docs/user-guide.md#对话助手) |
| 同步到 Notion | 详情或批量栏点「同步 Notion」 | [使用指南 · Notion](docs/user-guide.md#同步-notion) |
| B 站页一键导入 | 安装 Chrome 扩展 **chromematools** | [使用指南 · Chrome 扩展](docs/user-guide.md#chrome-扩展-b-站一键导入) |

## 文档索引

| 文档 | 适合谁 |
|------|--------|
| [**使用指南**](docs/user-guide.md) | 新用户：完整操作流程与界面说明 |
| [**配置说明**](docs/configuration.md) | 配 Cookie、LLM、Notion 的逐步说明 |
| [**API 参考**](docs/api.md) | 联调、脚本调用、接口字段 |
| [**开发说明**](docs/development.md) | 改代码：目录结构、自检、测试、Git |

## 功能一览

- B 站字幕 / 小红书笔记提取，自动去重与落盘
- 目录树笔记库（文件夹、拖拽、批量操作）
- Notion 按标题同步（同名覆盖）
- LLM 对话（@ / 拖拽引用笔记）
- Chrome 扩展 **chromematools** 从 B 站页导入（见 [使用指南](docs/user-guide.md#chrome-扩展-b-站一键导入)）

## 端口与命令速查

| 项 | 默认 |
|----|------|
| 前端 | 9177 |
| 后端 | 8907 |
| 启停 | `pm2 start/stop/restart ecosystem.config.cjs` |
| 日志 | `pm2 logs` |
