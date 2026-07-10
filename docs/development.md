# 开发说明

## 目录结构

```
ai-07-b-subtitle/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # subtitle、settings、chat
│   │   ├── services/        # bilibili、xiaohongshu、notion_sync、stores
│   │   ├── runtime/         # 对话 Agent 流水线
│   │   └── models/
│   ├── data/                # 本地数据（.gitignore）
│   └── requirements.txt
├── frontend/
│   ├── src/                 # App、LibraryTree、ChatPanel、SettingsPage
│   └── tests/               # Vitest
├── docs/                    # 本文档目录
└── ecosystem.config.cjs     # pm2
```

## 本地开发

### pm2

```bash
pm2 start ecosystem.config.cjs
pm2 logs
pm2 restart ecosystem.config.cjs
```

### 手动

```bash
# 后端
cd backend && source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8907 --reload --reload-dir app

# 前端
cd frontend && npm run dev -- --host 0.0.0.0 --port 9177
```

前端 `vite.config.js` 将 `/api` 代理到 `8907`。

## 数据持久化

| 路径 | 内容 |
|------|------|
| `data/subtitles/{id}.json` | 笔记正文、folder_id、notion_page_id 等 |
| `data/folders.json` | 文件夹树 |
| `data/chat_sessions/*.json` | 对话历史 |
| `data/settings.json` | 密钥与配置 |

去重键：B 站 `{bvid}_p{page}_{lan}`；小红书 `xhs_{note_id}`。

## 技术要点

- **抓取**：`httpx` + B 站 WBI 签名；小红书 edith / `__INITIAL_STATE__`
- **Notion**：`PATCH /pages/{id}/markdown` `replace_content`；标题 search + `notion_page_id` 缓存
- **对话**：OpenAI 兼容 SSE；`reference_record_ids` 注入笔记

## Agent Runtime

`backend/app/runtime/`：通用内核 + `plugins/note_library.py`。

```
Pipeline: Router → Planner → Confirm? → Executor
```

扩展：实现 `RuntimePlugin`，注册到 `Pipeline(plugins=[...])`。

```bash
python -m app.runtime.pipeline
python -m app.runtime.plugins.note_library
```

## 自检

```bash
cd backend && source .venv/bin/activate
python -m app.services.bilibili
python -m app.services.subtitle_store
python -m app.services.notion_sync
python -m app.services.chat_store
python -m app.api.v1.subtitle

cd ../frontend && npm test
```

## Git

```bash
git remote add origin <url>
git push -u origin main
```

敏感配置与本地数据勿提交：`backend/data/`、`.env`。
