# ai-07-b-subtitle

B 站视频 **字幕提取与管理** demo：输入视频链接 → 解析 BV → 拉取 CC / AI 字幕并展示。

技术栈：**FastAPI + httpx**（后端）+ **Vite + Vue 3**（前端），与 `projects/ai-*` 家族结构一致。

## 功能（当前 demo）

- 支持 `bilibili.com/video/BV…`、`av…`、`b23.tv` 短链
- 多分 P（`page` 参数）
- 自动选择中文字幕轨
- **本地字幕库**：提取后自动保存（`backend/data/subtitles/` JSON）
- **去重提取**：同一 `bvid + page + 字幕轨 lan` 仅保留一条；重复时提示，传 `force: true` 可强制重新拉取
- **批量管理**：侧栏卡片多选、全选、批量删除 / 复制 / 导出 txt·json
- **设置页**（右上角）：配置 `bilibili_sessdata`，存 `backend/data/settings.json`（GET 脱敏展示）

> 说明：B 站大量视频字幕需登录 Cookie。在 UI **设置** 中填写 **SESSDATA**，或 fallback 至 `backend/.env` 的 `BILIBILI_SESSDATA`。

## 开发

**一键启停**：

```bash
cd projects/ai-07-b-subtitle
chmod +x scripts/dev.sh
./scripts/dev.sh dev       # 前台 + 热更（推荐）
./scripts/dev.sh restart   # 后台 start | stop | status
# 后端 http://localhost:8907  前端 http://localhost:9177
# 日志：.run/logs/
```

热更：后端 `uvicorn --reload`（`backend/app/`）；前端 Vite HMR（`frontend/src/`）。

**手动启动**：

```bash
cd projects/ai-07-b-subtitle/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8907 --reload --reload-dir app

cd ../frontend
npm install && npm run dev -- --host 0.0.0.0 --port 9177
# 浏览器 http://localhost:9177
```

## API

- 健康检查：`GET /api/health`
- 提取字幕：`POST /api/v1/subtitle/extract`  
  Body: `{"url":"https://www.bilibili.com/video/BV…","page":1,"force":false}`
- 字幕库：`GET|DELETE /api/v1/subtitle/records`、`GET /api/v1/subtitle/records/{id}`  
  `POST /api/v1/subtitle/records/batch-delete`、`POST .../batch-export`（`format`: `txt`|`json`）
- 设置：`GET|PATCH /api/v1/settings` — 字段 `bilibili_sessdata`（响应脱敏）

## 数据目录

| 路径 | 内容 |
|------|------|
| `backend/data/subtitles/*.json` | 字幕记录 |
| `backend/data/settings.json` | SESSDATA 等应用设置（勿提交） |

## 自检

```bash
cd backend && python -m app.services.bilibili
cd backend && python -m app.services.subtitle_store
cd backend && python -m app.api.v1.subtitle
```

## Git

本目录为**独立仓库**：在 `projects/ai-07-b-subtitle` 内执行 `git remote add` / `git push`。

共性说明见仓库根目录 `docs/ai-projects-family.md`。
