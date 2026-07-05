"""链接平台识别。"""
from __future__ import annotations

import re

from app.services.bilibili import BV_RE, parse_bilibili_ref
from app.services.xiaohongshu import parse_xhs_ref, XhsError

BILI_HOSTS = ("bilibili.com", "b23.tv", "bili2233.cn")
XHS_HOSTS = ("xiaohongshu.com", "xhslink.com", "xhs.cn")


def detect_platform(raw: str) -> str:
    text = (raw or "").strip().lower()
    if not text:
        raise ValueError("请输入链接")

    for host in XHS_HOSTS:
        if host in text:
            return "xiaohongshu"

    if text.startswith("http"):
        from urllib.parse import urlparse

        host = urlparse(text).netloc.lower()
        for h in XHS_HOSTS:
            if h in host:
                return "xiaohongshu"
        for h in BILI_HOSTS:
            if h in host:
                return "bilibili"

    for host in BILI_HOSTS:
        if host in text:
            return "bilibili"

    if BV_RE.search(text) or re.search(r"\bav\d+\b", text, re.I):
        return "bilibili"

    try:
        parse_xhs_ref(text)
        return "xiaohongshu"
    except XhsError:
        pass

    try:
        parse_bilibili_ref(text)
        return "bilibili"
    except Exception:
        pass

    raise ValueError("无法识别平台，请粘贴 B 站或小红书笔记链接")


def _self_check() -> None:
    assert detect_platform("https://www.bilibili.com/video/BV1xx") == "bilibili"
    assert detect_platform("https://www.xiaohongshu.com/explore/656abc123def456789012345") == "xiaohongshu"
    assert detect_platform("https://xhslink.com/a/xxx") == "xiaohongshu"


if __name__ == "__main__":
    _self_check()
    print("platform self-check ok")
