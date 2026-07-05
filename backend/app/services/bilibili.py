"""B 站视频字幕抓取（player/v2 + WBI 签名，可选 SESSDATA）。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from app.services import settings_store

BV_RE = re.compile(r"(BV[a-zA-Z0-9]{10})", re.I)
AV_RE = re.compile(r"\bav(\d+)\b", re.I)
AID_RE = re.compile(r"[?&]aid=(\d+)", re.I)

WBI_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class BilibiliError(Exception):
    def __init__(self, message: str, *, need_login: bool = False) -> None:
        super().__init__(message)
        self.need_login = need_login


@dataclass
class VideoRef:
    bvid: str | None = None
    aid: int | None = None


@dataclass
class SubtitleResult:
    bvid: str
    aid: int
    cid: int
    title: str
    page: int
    page_title: str
    tracks: list[dict[str, Any]]
    selected: dict[str, Any] | None
    lines: list[dict[str, Any]]
    need_login: bool
    hint: str


def _mixin_key(raw: str) -> str:
    return "".join(raw[i] for i in WBI_ENC_TAB)[:32]


def _wbi_keys(img_url: str, sub_url: str) -> tuple[str, str]:
    def one(url: str) -> str:
        m = re.search(r"/([0-9a-f]+)\.(?:png|jpg|webp)", url, re.I)
        return m.group(1) if m else ""

    return one(img_url), one(sub_url)


def _wbi_sign(params: dict[str, Any], img_key: str, sub_key: str) -> dict[str, str]:
    signed = {k: "".join(str(v).split()) for k, v in sorted(params.items())}
    signed["wts"] = str(int(time.time()))
    query = urlencode(signed)
    signed["w_rid"] = hashlib.md5((query + _mixin_key(img_key + sub_key)).encode()).hexdigest()
    return signed


def parse_bilibili_ref(raw: str) -> VideoRef:
    text = (raw or "").strip()
    if not text:
        raise BilibiliError("请输入 B 站链接或 BV/av 号")

    m = BV_RE.search(text)
    if m:
        return VideoRef(bvid=m.group(1))

    m = AV_RE.search(text) or AID_RE.search(text)
    if m:
        return VideoRef(aid=int(m.group(1)))

    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        qs = parse_qs(parsed.query)
        if "bvid" in qs and qs["bvid"]:
            return VideoRef(bvid=qs["bvid"][0])
        if "aid" in qs and qs["aid"][0].isdigit():
            return VideoRef(aid=int(qs["aid"][0]))
        path = parsed.path or ""
        m = BV_RE.search(path) or AV_RE.search(path)
        if m:
            if m.group(0).lower().startswith("av"):
                return VideoRef(aid=int(m.group(1)))
            return VideoRef(bvid=m.group(1))

    raise BilibiliError("无法识别 BV 号或 av 号，请粘贴完整视频链接")


def _client_headers(sessdata: str | None) -> dict[str, str]:
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com"}
    if sessdata:
        headers["Cookie"] = f"SESSDATA={sessdata}"
    return headers


def _normalize_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    return url


def _format_time(sec: float) -> str:
    m = int(sec // 60)
    s = sec % 60
    return f"{m:02d}:{s:05.2f}"


def format_subtitle_text(lines: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in lines:
        content = (row.get("content") or "").strip()
        if not content:
            continue
        parts.append(f"[{_format_time(float(row.get('from', 0)))}] {content}")
    return "\n".join(parts)


def _pick_track(tracks: list[dict[str, Any]], lang: str | None) -> dict[str, Any] | None:
    if not tracks:
        return None
    if lang:
        lang_l = lang.lower()
        for t in tracks:
            if (t.get("lan") or "").lower() == lang_l:
                return t
        for t in tracks:
            doc = (t.get("lan_doc") or "").lower()
            if lang_l in doc or doc.startswith(lang_l):
                return t
    # 优先中文 / AI 中文
    for prefer in ("zh-cn", "zh", "ai-zh", "ai_zh"):
        for t in tracks:
            if (t.get("lan") or "").lower() == prefer:
                return t
    return tracks[0]


def _resolve_short_link(url: str, client: httpx.Client) -> str:
    host = urlparse(url).netloc.lower()
    if host.endswith("b23.tv") or host.endswith("bili2233.cn"):
        resp = client.get(url, follow_redirects=True)
        return str(resp.url)
    return url



def fetch_subtitles(
    raw_url: str,
    *,
    page: int = 1,
    lang: str | None = None,
    sessdata: str | None = None,
    timeout: float = 20.0,
) -> SubtitleResult:
    sessdata = sessdata or settings_store.get_bilibili_sessdata()
    headers = _client_headers(sessdata)

    with httpx.Client(
        headers=headers, timeout=timeout, follow_redirects=True, trust_env=False
    ) as client:
        resolved = _resolve_short_link(raw_url.strip(), client) if raw_url.strip().startswith("http") else raw_url
        ref = parse_bilibili_ref(resolved)

        view_params: dict[str, Any] = {}
        if ref.bvid:
            view_params["bvid"] = ref.bvid
        elif ref.aid:
            view_params["aid"] = ref.aid
        else:
            raise BilibiliError("缺少 bvid / aid")

        view_resp = client.get("https://api.bilibili.com/x/web-interface/view", params=view_params)
        view_resp.raise_for_status()
        view_json = view_resp.json()
        if view_json.get("code") != 0:
            raise BilibiliError(view_json.get("message") or "获取视频信息失败")

        data = view_json["data"]
        bvid = data.get("bvid") or ref.bvid or ""
        aid = int(data["aid"])
        title = data.get("title") or ""
        pages = data.get("pages") or []
        if not pages:
            raise BilibiliError("视频无分 P 信息")
        if page < 1 or page > len(pages):
            raise BilibiliError(f"分 P 超出范围（1-{len(pages)}）")

        part = pages[page - 1]
        cid = int(part["cid"])
        page_title = part.get("part") or f"P{page}"

        nav = client.get("https://api.bilibili.com/x/web-interface/nav").json()
        img_key, sub_key = _wbi_keys(
            nav.get("data", {}).get("wbi_img", {}).get("img_url", ""),
            nav.get("data", {}).get("wbi_img", {}).get("sub_url", ""),
        )
        signed = _wbi_sign({"aid": aid, "cid": cid, "bvid": bvid}, img_key, sub_key)
        player_resp = client.get("https://api.bilibili.com/x/player/wbi/v2", params=signed)
        player_resp.raise_for_status()
        player_json = player_resp.json()
        if player_json.get("code") != 0:
            raise BilibiliError(player_json.get("message") or "获取播放器信息失败")

        pdata = player_json.get("data") or {}
        need_login = bool(pdata.get("need_login_subtitle"))
        tracks = list((pdata.get("subtitle") or {}).get("subtitles") or [])

        hint = ""
        if not tracks:
            view_subs = list((data.get("subtitle") or {}).get("list") or [])
            if need_login and not sessdata:
                hint = (
                    "未获取到字幕：请在右上角「设置」中配置 BILIBILI SESSDATA（浏览器 Cookie）。"
                    "部分 AI/CC 字幕仅登录后可见。"
                )
                raise BilibiliError(hint, need_login=True)
            if view_subs:
                raise BilibiliError("字幕列表存在但下载地址为空，请稍后重试或换分 P")
            raise BilibiliError("该视频暂无可用字幕（可能未上传 CC / AI 字幕）")

        selected = _pick_track(tracks, lang)
        if not selected or not selected.get("subtitle_url"):
            raise BilibiliError("未找到可下载的字幕轨道")

        sub_url = _normalize_url(str(selected["subtitle_url"]))
        sub_resp = client.get(sub_url)
        sub_resp.raise_for_status()
        sub_json = sub_resp.json()
        lines = list(sub_json.get("body") or [])

        return SubtitleResult(
            bvid=bvid,
            aid=aid,
            cid=cid,
            title=title,
            page=page,
            page_title=page_title,
            tracks=tracks,
            selected=selected,
            lines=lines,
            need_login=need_login,
            hint=hint,
        )


def _self_check() -> None:
    assert parse_bilibili_ref("BV1GJ411x7h7").bvid == "BV1GJ411x7h7"
    assert parse_bilibili_ref("https://www.bilibili.com/video/BV1GJ411x7h7").bvid == "BV1GJ411x7h7"
    assert parse_bilibili_ref("av80433022").aid == 80433022
    sample = [{"from": 0.0, "to": 1.2, "content": "你好"}]
    assert "00:00.00" in format_subtitle_text(sample)
    assert "你好" in format_subtitle_text(sample)


if __name__ == "__main__":
    _self_check()
    print("bilibili self-check ok")
