# ai-07-b-subtitle

B 站视频 **字幕提取与管理** demo：输入视频链接 → 解析 BV → 拉取 CC / AI 字幕并展示。

技术栈：**FastAPI + httpx**（后端）+ **Vite + Vue 3**（前端），与 `projects/ai-*` 家族结构一致。

## 功能（当前 demo）

- 支持 `bilibili.com/video/BV…`、`av…`、`b23.tv` 短链
- 多分 P（`page` 参数）
- 自动选择中文字幕轨
- **本地字幕库**：提取后保存、列表查看、删除（`backend/data/subtitles/`）
- **去重提取**：同一 `bvid + page + 字幕轨 lan` 仅保留一条；重复提取时返回本地已有记录（`duplicate: true`），传 `force: true` 可强制重新拉取
- **批量管理**：侧栏多选、全选、批量删除 / 复制 / 导出 txt·json
- 前端展示带时间轴的纯文本，可一键复制

> 说明：B 站大量视频的字幕接口返回 `need_login_subtitle=true`，需在 `backend/.env` 配置浏览器 **`BILIBILI_SESSDATA`** Cookie 后才能拉取。

## 开发

**一键启停**（推荐）：

```bash
cd projects/ai-07-b-subtitle
chmod +x scripts/dev.sh
./scripts/dev.sh dev       # 前台 + 热更（改代码自动生效，推荐）
./scripts/dev.sh restart   # 后台 start | stop | status
# 后端 http://localhost:8907  前端 http://localhost:9177
# 日志：.run/logs/
```

热更说明：
- **后端**：`uvicorn --reload`，修改 `backend/app/` 下 Python 自动重启
- **前端**：Vite HMR，修改 `frontend/src/` 自动刷新
- 关闭热更：`UVICORN_RELOAD=0 ./scripts/dev.sh start`

手动启动：
cd projects/ai-07-b-subtitle/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 可选：填写 BILIBILI_SESSDATA
uvicorn app.main:app --host 0.0.0.0 --port 8907

cd ../frontend
npm install && npm run dev
# 浏览器 http://localhost:9177
```

- 健康检查：`GET http://localhost:8907/api/health`
- 提取字幕：`POST /api/v1/subtitle/extract`  
  Body: `{"url":"https://www.bilibili.com/video/BV…","page":1,"save":true,"force":false}`
  - 命中本地记录时返回 `duplicate: true` + `existing_record_id`，不调用 B 站 API
- 字幕库：
  - `GET /api/v1/subtitle/records`
  - `GET /api/v1/subtitle/records/{id}`
  - `DELETE /api/v1/subtitle/records/{id}`
  - `POST /api/v1/subtitle/records/batch-delete` — body: `{"ids":["id1","id2"]}`
  - `POST /api/v1/subtitle/records/batch-export` — body: `{"ids":["id1"],"format":"txt"}`（`format` 可为 `txt` / `json`）
- 设置（UI 右上角入口）：`GET/PATCH /api/v1/settings` — 仅 `bilibili_sessdata`，存 `backend/data/settings.json`

## 自检

```bash
cd backend && python -m app.services.bilibili
cd backend && python -m app.services.subtitle_store
cd backend && python -m app.api.v1.subtitle   # TestClient API 冒烟（含去重）
```

## Git

本目录为**独立仓库**：在 `projects/ai-07-b-subtitle` 内执行 `git remote add` / `git push`。

共性说明见仓库根目录 `docs/ai-projects-family.md`。
