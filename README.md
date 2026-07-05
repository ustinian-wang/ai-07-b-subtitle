# ai-07-b-subtitle

**B 站视频字幕提取与管理** 教学沙箱（FastAPI + httpx + Vue 3 + Vite）。输入视频链接 → 解析 BV/av → 拉取 CC / AI 字幕 → 本地 JSON 库持久化、去重与批量导出。

> 本目录为 **独立 Git 仓库**，可在 monorepo 的 `projects/` 下单独 clone / push，与 `ai-01-chat` 等家族项目结构对齐。共性约定见 monorepo 根目录 [`docs/ai-projects-family.md`](../../docs/ai-projects-family.md)（若仅 clone 本子仓，可忽略该链接）。

## 功能

- 支持 `bilibili.com/video/BV…`、`av…`、`b23.tv` / `bili2233.cn` 短链
- 多分 P（`page` 参数，从 1 开始）
- 自动优先选择中文字幕轨（`zh-cn` / `zh` / `ai-zh` 等）
- **提取后自动保存**到本地字幕库（`backend/data/subtitles/*.json`）
- **去重**：同一 `bvid + page + 字幕轨 lan` 仅一条；重复提取时提示，可查看已有或 `force: true` 强制重拉
- **字幕库侧栏**：卡片列表、多选、全选、批量删除 / 复制 / 导出 txt·json
- **设置页**（右上角）：配置 B 站登录 Cookie **`SESSDATA`**，存 `backend/data/settings.json`（API 响应脱敏）
- **开发热更**：`scripts/dev.sh dev` 或 `uvicorn --reload` + Vite HMR

## 目录结构

```
ai-07-b-subtitle/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # subtitle、settings 路由
│   │   ├── services/        # bilibili 抓取、subtitle_store、settings_store
│   │   └── models/          # Pydantic schemas
│   ├── data/                # 本地数据（.gitignore，不入库）
│   │   ├── subtitles/       # 字幕记录 *.json
│   │   └── settings.json    # SESSDATA 等
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/App.vue          # 主界面 + 字幕库侧栏
│   └── src/SettingsPage.vue # 设置页
├── scripts/dev.sh           # start | stop | restart | dev | status
└── README.md
```

## 开发

### 一键启停（推荐）

```bash
cd projects/ai-07-b-subtitle   # 或 clone 后的项目根目录
chmod +x scripts/dev.sh
./scripts/dev.sh dev           # 前台 + 热更（改代码自动生效）
./scripts/dev.sh restart       # 后台运行
./scripts/dev.sh status        # 查看状态
./scripts/dev.sh stop          # 停止
```

### 手动启动

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8907 --reload --reload-dir app

cd ../frontend
npm install && npm run dev -- --host 0.0.0.0 --port 9177
```

| 项 | 默认值 |
|----|--------|
| 后端地址 | http://localhost:8907 |
| 前端地址 | http://localhost:9177 |
| 健康检查 | `GET /api/health` |
| 热更 | 后端 `backend/app/`；前端 Vite HMR |
| 日志（脚本后台模式） | `.run/logs/` |

## 配置：B 站 SESSDATA

大量 B 站视频的字幕接口返回 `need_login_subtitle=true`，需登录 Cookie 才能拉取 CC / AI 字幕。

**推荐**：浏览器打开前端 → 右上角 **设置** → 粘贴 `SESSDATA` → 保存。

| 方式 | 说明 |
|------|------|
| **UI 设置页** | 写入 `backend/data/settings.json`，GET API 仅返回脱敏值（如 `9f8e****IIEC`） |
| **环境变量 fallback** | `backend/.env` 中 `BILIBILI_SESSDATA=`（settings 未配置时使用） |

获取 Cookie：浏览器登录 [bilibili.com](https://www.bilibili.com) → F12 → Application → Cookies → 复制 `SESSDATA` 的值。

> **安全**：`backend/data/`、`.env` 已在 `.gitignore`，勿将 SESSDATA 提交进 Git。

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/v1/subtitle/extract` | 提取字幕；body 见下 |
| POST | `/api/v1/subtitle/save` | 手动保存（一般无需，提取已自动落盘） |
| GET | `/api/v1/subtitle/records` | 字幕库列表（摘要） |
| GET | `/api/v1/subtitle/records/{id}` | 单条字幕详情 |
| DELETE | `/api/v1/subtitle/records/{id}` | 删除一条 |
| POST | `/api/v1/subtitle/records/batch-delete` | 批量删除，`{"ids":["id1","id2"]}` |
| POST | `/api/v1/subtitle/records/batch-export` | 批量导出，`{"ids":[...],"format":"txt"\|"json"}` |
| GET | `/api/v1/settings` | 读取设置（SESSDATA 脱敏） |
| PATCH | `/api/v1/settings` | 更新设置，`{"bilibili_sessdata":"..."}`，空字符串可清除 |

### 提取字幕 `POST /api/v1/subtitle/extract`

```json
{
  "url": "https://www.bilibili.com/video/BV1Eb411u7Fw",
  "page": 1,
  "lang": null,
  "force": false
}
```

| 字段 | 说明 |
|------|------|
| `url` | B 站链接、BV 号或 av 号 |
| `page` | 分 P 序号，默认 1 |
| `lang` | 可选，优先字幕语言，如 `zh-CN` |
| `force` | `true` 时忽略本地去重，重新请求 B 站并 upsert |

**去重命中**时返回 `duplicate: true`、`existing_record_id`，不调用 B 站 API；前端会提示「直接查看」或「重新提取」。

**成功提取**时自动 upsert 到 `data/subtitles/`，响应含 `record_id`、`lines`、`text`（带时间轴纯文本）。

## 数据持久化

| 路径 | 内容 |
|------|------|
| `backend/data/subtitles/{id}.json` | 单条字幕：bvid、title、lines、text、dedupe_key、时间戳等 |
| `backend/data/settings.json` | 应用设置（当前仅 `bilibili_sessdata`） |

- **去重键**：`{bvid}_p{page}_{lan}`，同键 upsert 更新而非新建文件
- **本地数据不入 Git**：`backend/data/`、`.run/` 已在 `.gitignore`

## 技术说明

- **无 LLM**：后端通过 `httpx` 调用 B 站公开 API（`view` → `player/wbi/v2` → 字幕 JSON），不依赖 OpenAI
- **WBI 签名**：player 接口需 nav 接口提供的 img/sub key 签名
- **代理**：前端 Vite 将 `/api` 代理到 `http://127.0.0.1:8907`（见 `frontend/vite.config.js`）

## 自检

```bash
cd backend && source .venv/bin/activate
python -m app.services.bilibili      # URL 解析、时间格式
python -m app.services.subtitle_store
python -m app.api.v1.subtitle        # TestClient 冒烟（含去重、批量导出）
```

## 独立仓库与 Git

```bash
# 在 projects/ai-07-b-subtitle 目录内
git remote add origin <你的远程仓库 URL>
git push -u origin main
```

- 由 monorepo 脚本生成时：`./scripts/add-ai-project.sh b-subtitle` → 目录名 `ai-07-b-subtitle`
- 父 monorepo **不要**把子目录内的 `.git` 当普通文件夹提交

## 相关文档

- 家族项目对照与端口表：monorepo [`docs/ai-projects-family.md`](../../docs/ai-projects-family.md)
- 新建同类沙箱：monorepo `scripts/add-ai-project.sh` 或 Cursor 命令 `/add-ai-project`
