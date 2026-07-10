"""Notion 笔记同步：按标题 upsert 到 parent 子页面。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services import settings_store
from app.services.subtitle_store import get_record, infer_source, save_record

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionSyncError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_notion_title(record: dict[str, Any]) -> str:
    """本地笔记标题；B 站分 P>1 时加 (P{n}) 后缀。"""
    title = (record.get("title") or "").strip() or "未命名笔记"
    source = infer_source(record)
    page = int(record.get("page") or 1)
    if source == "bilibili" and page > 1:
        return f"{title} (P{page})"
    return title


def build_notion_markdown(record: dict[str, Any]) -> str:
    """来源元信息 + 正文。"""
    source = infer_source(record)
    lines = [
        "## 来源信息",
        "",
        f"- **平台**: {'B站' if source == 'bilibili' else '小红书'}",
        f"- **标题**: {record.get('title') or ''}",
    ]
    if source == "bilibili":
        lines.extend(
            [
                f"- **BV号**: {record.get('bvid') or ''}",
                f"- **分P**: {int(record.get('page') or 1)}",
            ]
        )
        if record.get("page_title"):
            lines.append(f"- **分P标题**: {record.get('page_title')}")
        track = record.get("selected_track") or {}
        if track.get("lan_doc") or track.get("lan"):
            lines.append(f"- **字幕轨**: {track.get('lan_doc') or track.get('lan')}")
    else:
        lines.extend(
            [
                f"- **笔记ID**: {record.get('note_id') or ''}",
                f"- **类型**: {record.get('note_type') or ''}",
            ]
        )
        if record.get("author"):
            lines.append(f"- **作者**: {record.get('author')}")
        tags = record.get("tags") or []
        if tags:
            lines.append(f"- **标签**: {', '.join(str(t) for t in tags)}")
    if record.get("source_url"):
        lines.append(f"- **链接**: {record.get('source_url')}")
    lines.extend(["", "---", "", record.get("text") or ""])
    return "\n".join(lines)


def _extract_page_title(page: dict[str, Any]) -> str:
    props = page.get("properties") or {}
    for prop in props.values():
        if not isinstance(prop, dict) or prop.get("type") != "title":
            continue
        chunks = prop.get("title") or []
        return "".join(part.get("plain_text") or "" for part in chunks)
    return ""


def _notion_headers() -> dict[str, str]:
    token = settings_store.get_notion_token()
    if not token:
        raise NotionSyncError("Notion Token 未配置，请前往设置页填写")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _notion_request(method: str, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{NOTION_API}{path}"
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.request(method, url, headers=_notion_headers(), json=json_body)
    except httpx.HTTPError as exc:
        raise NotionSyncError(f"Notion 网络错误: {exc}") from exc

    if resp.status_code >= 400:
        detail = resp.text.strip()
        try:
            payload = resp.json()
            detail = payload.get("message") or detail
        except ValueError:
            pass
        raise NotionSyncError(f"Notion API {resp.status_code}: {detail}")

    if not resp.content:
        return {}
    try:
        data = resp.json()
    except ValueError as exc:
        raise NotionSyncError("Notion 响应非 JSON") from exc
    return data if isinstance(data, dict) else {}


def find_page_by_title(title: str) -> str | None:
    """POST /v1/search，精确标题匹配，返回 page_id 或 None。"""
    parent_id = settings_store.get_notion_parent_id()
    if not parent_id:
        raise NotionSyncError("Notion 父页面 ID 未配置，请前往设置页填写")

    data = _notion_request(
        "POST",
        "/search",
        {
            "query": title,
            "filter": {"property": "object", "value": "page"},
            "page_size": 100,
        },
    )
    matches: list[str] = []
    for item in data.get("results") or []:
        if item.get("object") != "page":
            continue
        parent = item.get("parent") or {}
        if parent.get("page_id") != parent_id:
            continue
        if _extract_page_title(item) == title:
            page_id = item.get("id")
            if page_id:
                matches.append(page_id)

    if not matches:
        return None
    if len(matches) > 1:
        # ponytail: 同名多页取第一个；升级路径：返回 failed 或让用户手动指定
        logger.warning("Notion 同名页面 %d 个，取第一个: %s", len(matches), title)
    return matches[0]


def create_page(title: str, markdown: str) -> str:
    """在 parent 下创建子页面。"""
    parent_id = settings_store.get_notion_parent_id()
    if not parent_id:
        raise NotionSyncError("Notion 父页面 ID 未配置，请前往设置页填写")

    data = _notion_request(
        "POST",
        "/pages",
        {
            "parent": {"page_id": parent_id},
            "properties": {
                "title": {
                    "title": [{"text": {"content": title[:2000]}}],
                }
            },
            "markdown": markdown,
        },
    )
    page_id = data.get("id")
    if not page_id:
        raise NotionSyncError("Notion 创建页面未返回 id")
    return page_id


def replace_page_content(page_id: str, markdown: str) -> None:
    """PATCH /v1/pages/{id}/markdown replace_content。"""
    _notion_request(
        "PATCH",
        f"/pages/{page_id}/markdown",
        {
            "type": "replace_content",
            "replace_content": {"new_str": markdown},
        },
    )


def _resolve_page_id(title: str, cached_page_id: str | None) -> tuple[str | None, bool]:
    """返回 (page_id, used_cache)。"""
    if cached_page_id:
        return cached_page_id, True
    return find_page_by_title(title), False


def sync_record(record_id: str) -> dict[str, Any]:
    """完整 upsert：缓存 page_id 优先，否则按标题查找/创建，并回写本地。"""
    if not settings_store.notion_configured():
        raise NotionSyncError("Notion 未配置，请前往设置页填写 Token 与父页面 ID")

    record = get_record(record_id)
    if not record:
        raise NotionSyncError("记录不存在")

    title = build_notion_title(record)
    markdown = build_notion_markdown(record)
    cached_page_id = (record.get("notion_page_id") or "").strip() or None
    page_id, used_cache = _resolve_page_id(title, cached_page_id)
    action = "updated"

    if page_id:
        try:
            replace_page_content(page_id, markdown)
        except NotionSyncError:
            if used_cache:
                page_id = find_page_by_title(title)
                if page_id:
                    replace_page_content(page_id, markdown)
                else:
                    page_id = create_page(title, markdown)
                    action = "created"
            else:
                raise
    else:
        page_id = create_page(title, markdown)
        action = "created"

    save_record(
        {
            **record,
            "notion_page_id": page_id,
            "notion_synced_at": _now_iso(),
        }
    )
    return {
        "id": record_id,
        "notion_page_id": page_id,
        "action": action,
        "title": title,
    }


def batch_sync_records(record_ids: list[str]) -> dict[str, list[Any]]:
    synced: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for rid in record_ids:
        try:
            synced.append(sync_record(rid))
        except NotionSyncError as exc:
            failed.append({"id": rid, "error": str(exc)})
        except Exception as exc:  # ponytail: 单条失败不中断批量
            failed.append({"id": rid, "error": str(exc)})
    return {"synced": synced, "failed": failed}


def _self_check() -> None:
    bili_p1 = {
        "source": "bilibili",
        "title": "测试视频",
        "page": 1,
        "bvid": "BV1test",
        "source_url": "https://www.bilibili.com/video/BV1test",
        "text": "正文",
    }
    assert build_notion_title(bili_p1) == "测试视频"
    bili_p2 = {**bili_p1, "page": 2}
    assert build_notion_title(bili_p2) == "测试视频 (P2)"

    xhs = {
        "source": "xiaohongshu",
        "title": "小红书笔记",
        "note_id": "abc123",
        "tags": ["tag1"],
        "text": "笔记正文",
    }
    assert build_notion_title(xhs) == "小红书笔记"
    md = build_notion_markdown(xhs)
    assert "小红书" in md
    assert "abc123" in md
    assert "笔记正文" in md

    assert _extract_page_title(
        {"properties": {"Name": {"type": "title", "title": [{"plain_text": "Hello"}]}}}
    ) == "Hello"


if __name__ == "__main__":
    _self_check()
    print("notion_sync self-check ok")
