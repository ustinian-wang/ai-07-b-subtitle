# API 参考

Base URL：`http://localhost:8907`（前端经 Vite 代理 `/api`）。

## 健康检查

```bash
GET /api/health
```

## 笔记库 ` /api/v1/subtitle`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/extract` | 提取并保存（自动识别平台） |
| POST | `/save` | 手动保存（一般无需） |
| GET | `/tree` | 目录树 |
| GET | `/records` | 扁平列表 |
| GET | `/records/{id}` | 单条详情 |
| DELETE | `/records/{id}` | 删除 |
| POST | `/records/batch-move` | 批量移动 |
| POST | `/records/batch-delete` | 批量删除 |
| POST | `/records/batch-export` | 批量导出 `txt` / `json` |
| POST | `/records/batch-sync-notion` | 批量同步 Notion |
| POST | `/folders` | 新建文件夹 |
| PATCH | `/folders/{id}` | 重命名 / 移动文件夹 |
| DELETE | `/folders/{id}` | 删除文件夹 |

### 提取 `POST /api/v1/subtitle/extract`

B 站：

```json
{
  "url": "https://www.bilibili.com/video/BV1Eb411u7Fw",
  "page": 1,
  "lang": null,
  "force": false,
  "folder_id": null
}
```

小红书：

```json
{
  "url": "https://www.xiaohongshu.com/explore/656abc...",
  "force": false,
  "folder_id": null
}
```

| 字段 | 说明 |
|------|------|
| `url` | B 站 / 小红书链接 |
| `page` | B 站分 P，默认 1 |
| `lang` | 可选，B 站优先字幕语言 |
| `force` | `true` 忽略去重重拉 |
| `folder_id` | 保存到指定文件夹，`null` 为未分类 |

去重命中：`duplicate: true`、`existing_record_id`。  
成功：`record_id`、`text`、`lines`（B 站）等。

### Notion 同步 `POST /api/v1/subtitle/records/batch-sync-notion`

```json
{ "ids": ["990f0b94d324"] }
```

```json
{
  "ok": true,
  "synced": [
    {
      "id": "990f0b94d324",
      "notion_page_id": "39923c65-8d1e-81b4-8bc6-eb78a5f12d52",
      "action": "created",
      "title": "视频标题"
    }
  ],
  "failed": []
}
```

未配置 Notion → `400`：`Notion 未配置，请前往设置页填写 Integration Token 与父页面 ID`。

## 设置 ` /api/v1/settings`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `` | 读取（密钥脱敏） |
| PATCH | `` | 更新 `bilibili_sessdata`、`xiaohongshu_cookie`、`openai_*`、`notion_*` |

## 对话 ` /api/v1/chat`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/sessions` | 新建会话 |
| GET | `/sessions` | 会话列表 |
| DELETE | `/sessions/{thread_id}` | 删除会话 |
| GET | `/messages?thread_id=…` | 历史消息 |
| DELETE | `/messages?thread_id=…` | 清空会话 |
| POST | `/stream` | SSE 流式对话 |

### 流式对话 `POST /api/v1/chat/stream`

```json
{
  "thread_id": "abc123",
  "message": "总结这篇笔记的要点",
  "reference_record_ids": ["record_id_1"]
}
```

SSE：`data: {"delta":"…"}` → `data: {"done":true}`；错误 `data: {"error":"…"}`。

## Chrome 扩展调用链（chromematools）

```
GET /api/health
→ GET /api/v1/subtitle/tree
→ POST /api/v1/subtitle/folders（若无「B站资源」）
→ POST /api/v1/subtitle/extract
→ duplicate 时 POST /api/v1/subtitle/records/batch-move
```
