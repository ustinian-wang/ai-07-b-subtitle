# 配置说明

所有敏感项推荐在 **前端设置页** 填写，保存到 `backend/data/settings.json`（已 `.gitignore`）。  
也可用 `backend/.env` 作 fallback，模板见 `backend/.env.example`。

读取优先级：**settings.json > 环境变量**。

## 配置入口

http://localhost:9177 → 左下角 **设置**

查看当前状态（脱敏）：

```bash
curl http://localhost:8907/api/v1/settings
```

更新示例：

```bash
curl -X PATCH http://localhost:8907/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"bilibili_sessdata":"你的SESSDATA"}'
```

## B 站 SESSDATA

大量 B 站视频字幕接口返回 `need_login_subtitle=true`，需登录 Cookie。

1. 浏览器登录 bilibili.com
2. F12 → Application → Cookies → 复制 `SESSDATA`
3. 设置页粘贴 → 保存

| 环境变量 fallback | `BILIBILI_SESSDATA` |

## 小红书 Cookie

1. 浏览器登录 xiaohongshu.com
2. F12 → Cookies → 复制完整 Cookie 或关键字段
3. 设置页粘贴 → 保存

| 环境变量 fallback | `XIAOHONGSHU_COOKIE` |

## 对话 LLM（OpenAI 兼容）

右侧对话助手依赖 OpenAI 兼容 API。

| 字段 | 说明 | 默认 |
|------|------|------|
| `openai_api_key` | API Key（必填） | — |
| `openai_base_url` | 兼容端点 | `https://api.openai.com/v1` |
| `openai_model` | 模型名 | `gpt-4o-mini` |

| 环境变量 fallback | `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` |

可复制已有 OpenAI 兼容服务的 `.env` 中的 `OPENAI_*` 到本项目设置页或 `.env`（勿提交密钥）。

## Notion 同步

将笔记同步为 Notion **父页面下的子页面**；按标题匹配，同名 `replace_content` 覆盖。

### 准备步骤

1. [notion.so/my-integrations](https://www.notion.so/my-integrations) 创建 **Internal Integration**
2. Capabilities 勾选：**Read / Update / Insert content**
3. 复制 **Integration Secret**（`secret_…` 或 `ntn_…`）
4. 在 Notion 打开目标**普通页面**（非 Database），从 URL 取 32 位 **Page ID**
5. 该页面 **⋯ → Connections** → 添加你的 Integration（**必做**，否则 API 404）

### 设置页字段

| 字段 | 说明 |
|------|------|
| `notion_token` | Integration Secret |
| `notion_parent_id` | 父页面 Page ID |

| 环境变量 fallback | `NOTION_TOKEN`、`NOTION_PARENT_ID` |

Token 与父页面 ID **都填** 才算配置完成。

### 标题规则

- 默认：`record.title`
- B 站且 `page > 1`：`{title} (P{n})`

同步成功后本地 JSON 会写入 `notion_page_id`、`notion_synced_at` 加速下次更新。
