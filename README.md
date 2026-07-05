# ai-07-b-subtitle

B 站视频 **字幕提取与管理** demo：输入视频链接 → 解析 BV → 拉取 CC / AI 字幕并展示。

技术栈：**FastAPI + httpx**（后端）+ **Vite + Vue 3**（前端），与 `projects/ai-*` 家族结构一致。

## 功能（当前 demo）

- 支持 `bilibili.com/video/BV…`、`av…`、`b23.tv` 短链
- 多分 P（`page` 参数）
- 自动选择中文字幕轨
- **本地字幕库**：提取后保存、列表查看、删除（`backend/data/subtitles/`）
- 前端展示带时间轴的纯文本，可一键复制

> 说明：B 站大量视频的字幕接口返回 `need_login_subtitle=true`，需在 `backend/.env` 配置浏览器 **`BILIBILI_SESSDATA`** Cookie 后才能拉取。

## 开发

```bash
cd projects/ai-07-b-subtitle/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 可选：填写 BILIBILI_SESSDATA
uvicorn app.main:app --host 127.0.0.1 --port 8907

cd ../frontend
npm install && npm run dev
# 浏览器 http://127.0.0.1:9177
```

- 健康检查：`GET http://127.0.0.1:8907/api/health`
- 提取字幕：`POST /api/v1/subtitle/extract`  
  Body: `{"url":"https://www.bilibili.com/video/BV…","page":1,"save":true}`
- 字幕库：`GET /api/v1/subtitle/records`、`GET /api/v1/subtitle/records/{id}`、`DELETE /api/v1/subtitle/records/{id}`

## 自检

```bash
cd backend && python -m app.services.bilibili
cd backend && python -m app.services.subtitle_store
```

## Git

本目录为**独立仓库**：在 `projects/ai-07-b-subtitle` 内执行 `git remote add` / `git push`。

共性说明见仓库根目录 `docs/ai-projects-family.md`。
