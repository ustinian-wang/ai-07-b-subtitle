"""小红书笔记抓取（edith feed API + __INITIAL_STATE__ 回退）。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from app.services import settings_store

NOTE_ID_RE = re.compile(r"(?:explore|discovery/item|item)/([0-9a-f]{24})", re.I)
NOTE_ID_LOOSE_RE = re.compile(r"([0-9a-f]{24})", re.I)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class XhsError(Exception):
    def __init__(self, message: str, *, need_login: bool = False) -> None:
        super().__init__(message)
        self.need_login = need_login


@dataclass
class NoteRef:
    note_id: str
    xsec_token: str = ""


@dataclass
class NoteResult:
    note_id: str
    title: str
    desc: str
    note_type: str
    author: str
    tags: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    video_url: str = ""
    need_login: bool = False
    hint: str = ""


def parse_xhs_ref(raw: str) -> NoteRef:
    text = (raw or "").strip()
    if not text:
        raise XhsError("请输入小红书笔记链接")

    xsec_token = ""
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        qs = parse_qs(parsed.query)
        xsec_token = (qs.get("xsec_token") or [""])[0]
        path = parsed.path or ""
        m = NOTE_ID_RE.search(path) or NOTE_ID_RE.search(text)
        if m:
            return NoteRef(note_id=m.group(1).lower(), xsec_token=xsec_token)

    m = NOTE_ID_RE.search(text)
    if m:
        return NoteRef(note_id=m.group(1).lower(), xsec_token=xsec_token)

    m = NOTE_ID_LOOSE_RE.search(text)
    if m and len(m.group(1)) == 24:
        return NoteRef(note_id=m.group(1).lower(), xsec_token=xsec_token)

    raise XhsError("无法识别小红书笔记 ID，请粘贴完整分享链接")


def format_note_text(*, title: str, desc: str, tags: list[str]) -> str:
    parts: list[str] = []
    if title.strip():
        parts.append(title.strip())
    if desc.strip():
        parts.append(desc.strip())
    if tags:
        parts.append("")
        parts.append("标签: " + " ".join(f"#{t}" for t in tags if t))
    return "\n\n".join(parts).strip()


def _client_headers(cookie: str | None) -> dict[str, str]:
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.xiaohongshu.com/",
        "Origin": "https://www.xiaohongshu.com",
        "Content-Type": "application/json",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def _resolve_short_link(url: str, client: httpx.Client) -> str:
    host = urlparse(url).netloc.lower()
    if "xhslink.com" in host or "xhs.cn" in host:
        resp = client.get(url, follow_redirects=True)
        return str(resp.url)
    return url


def _pick_image_url(item: dict[str, Any]) -> str:
    for key in ("url_default", "url", "info_list"):
        val = item.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, dict):
                u = first.get("url") or first.get("url_default") or ""
                if u:
                    return u
    return ""


def _parse_note_card(card: dict[str, Any]) -> NoteResult:
    note_id = (card.get("note_id") or card.get("id") or "").lower()
    title = (card.get("title") or "").strip()
    desc = (card.get("desc") or card.get("description") or "").strip()
    note_type = (card.get("type") or "normal").lower()
    author = ((card.get("user") or {}).get("nickname") or "").strip()

    tags: list[str] = []
    for tag in card.get("tag_list") or card.get("tags") or []:
        if isinstance(tag, dict):
            name = (tag.get("name") or tag.get("tag") or "").strip()
        else:
            name = str(tag).strip()
        if name:
            tags.append(name.lstrip("#"))

    images: list[str] = []
    for img in card.get("image_list") or []:
        if isinstance(img, dict):
            url = _pick_image_url(img)
            if url:
                images.append(url)

    video_url = ""
    video = card.get("video") or {}
    if isinstance(video, dict):
        media = video.get("media") or video.get("consumer") or {}
        stream = (media.get("stream") or {}) if isinstance(media, dict) else {}
        for codec in ("h264", "h265", "av1"):
            items = stream.get(codec) if isinstance(stream, dict) else None
            if isinstance(items, list) and items:
                video_url = items[0].get("master_url") or items[0].get("backup_url") or ""
                if video_url:
                    break
        if not video_url:
            video_url = video.get("url") or video.get("media_url") or ""

    if note_type == "video" or video_url:
        note_type = "video"

    return NoteResult(
        note_id=note_id,
        title=title,
        desc=desc,
        note_type=note_type,
        author=author,
        tags=tags,
        images=images,
        video_url=video_url,
    )


def _fetch_via_feed_api(
    client: httpx.Client,
    *,
    note_id: str,
    xsec_token: str,
) -> NoteResult | None:
    payload: dict[str, Any] = {
        "source_note_id": note_id,
        "image_formats": ["jpg", "webp", "avif"],
        "extra": {"need_body_topic": "1"},
    }
    if xsec_token:
        payload["xsec_token"] = xsec_token
        payload["xsec_source"] = "pc_share"
    else:
        payload["xsec_source"] = "pc_feed"

    resp = client.post("https://edith.xiaohongshu.com/api/sns/web/v1/feed", json=payload)
    if resp.status_code >= 400:
        return None
    data = resp.json()
    if not data.get("success"):
        return None
    items = ((data.get("data") or {}).get("items") or [])
    if not items:
        return None
    card = items[0].get("note_card") or items[0].get("note") or items[0]
    if not isinstance(card, dict):
        return None
    return _parse_note_card(card)


def _extract_initial_state(html: str) -> dict[str, Any] | None:
    marker = "window.__INITIAL_STATE__="
    idx = html.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    end = html.find("</script>", start)
    if end < 0:
        return None
    raw = html[start:end].strip()
    if raw.endswith(";"):
        raw = raw[:-1]
    raw = raw.replace(":undefined", ":null").replace(",undefined", ",null")
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return state if isinstance(state, dict) else None


def _note_from_initial_state(state: dict[str, Any], note_id: str) -> NoteResult | None:
    detail_map = ((state.get("note") or {}).get("noteDetailMap") or {})
    node = detail_map.get(note_id) or {}
    note = node.get("note") if isinstance(node, dict) else None
    if not isinstance(note, dict):
        for val in detail_map.values():
            if isinstance(val, dict) and isinstance(val.get("note"), dict):
                note = val["note"]
                break
    if not isinstance(note, dict):
        return None
    return _parse_note_card(note)


def _fetch_via_html(
    client: httpx.Client,
    *,
    note_id: str,
    xsec_token: str,
) -> NoteResult | None:
    query = f"?xsec_token={xsec_token}&xsec_source=pc_share" if xsec_token else ""
    url = f"https://www.xiaohongshu.com/explore/{note_id}{query}"
    resp = client.get(url)
    if resp.status_code >= 400:
        return None
    state = _extract_initial_state(resp.text)
    if not state:
        return None
    return _note_from_initial_state(state, note_id)


def fetch_note(
    raw_url: str,
    *,
    cookie: str | None = None,
    timeout: float = 25.0,
) -> NoteResult:
    cookie = cookie or settings_store.get_xiaohongshu_cookie()

    with httpx.Client(
        headers=_client_headers(cookie),
        timeout=timeout,
        follow_redirects=True,
        trust_env=False,
    ) as client:
        resolved = (
            _resolve_short_link(raw_url.strip(), client)
            if raw_url.strip().startswith("http")
            else raw_url.strip()
        )
        ref = parse_xhs_ref(resolved)
        if not ref.xsec_token and resolved.startswith("http"):
            parsed = urlparse(resolved)
            ref.xsec_token = (parse_qs(parsed.query).get("xsec_token") or [""])[0]

        result = _fetch_via_feed_api(client, note_id=ref.note_id, xsec_token=ref.xsec_token)
        if not result:
            result = _fetch_via_html(client, note_id=ref.note_id, xsec_token=ref.xsec_token)

        if not result or not (result.title or result.desc):
            hint = (
                "无法获取笔记内容：请在「设置」中配置小红书 Cookie（登录 xiaohongshu.com 后 F12 复制），"
                "并尽量使用带 xsec_token 的完整分享链接。"
            )
            if not cookie:
                raise XhsError(hint, need_login=True)
            raise XhsError(hint)

        result.need_login = False
        result.hint = ""
        if not result.note_id:
            result.note_id = ref.note_id
        return result


def _self_check() -> None:
    ref = parse_xhs_ref("https://www.xiaohongshu.com/explore/656abc123def456789012345?xsec_token=abc")
    assert ref.note_id == "656abc123def456789012345"
    assert ref.xsec_token == "abc"

    card = {
        "note_id": "656abc123def456789012345",
        "title": "测试标题",
        "desc": "正文内容",
        "type": "normal",
        "user": {"nickname": "作者"},
        "tag_list": [{"name": "旅行"}],
        "image_list": [{"url_default": "https://example.com/a.jpg"}],
    }
    parsed = _parse_note_card(card)
    assert parsed.title == "测试标题"
    assert "旅行" in parsed.tags
    text = format_note_text(title=parsed.title, desc=parsed.desc, tags=parsed.tags)
    assert "正文内容" in text
    assert "#旅行" in text

    state = {
        "note": {
            "noteDetailMap": {
                "656abc123def456789012345": {"note": card},
            }
        }
    }
    from_state = _note_from_initial_state(state, "656abc123def456789012345")
    assert from_state and from_state.title == "测试标题"


if __name__ == "__main__":
    _self_check()
    print("xiaohongshu self-check ok")
