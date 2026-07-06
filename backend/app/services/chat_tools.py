"""对话助手内置工具：OpenAI function 定义 + 按分类执行。"""
from __future__ import annotations

import json
from typing import Any

from app.services.bilibili import BilibiliError, fetch_subtitles, format_subtitle_text, parse_bilibili_ref
from app.services.folder_store import (
    create_folder,
    get_folder,
    is_system_folder,
    is_uncategorized_folder_id,
    list_user_folders,
)
from app.services.platform import detect_platform
from app.services.subtitle_store import (
    delete_records,
    export_records,
    find_by_bvid_page,
    find_by_dedupe_key,
    find_by_xhs_note_id,
    get_record,
    infer_source,
    list_records,
    move_records_to_folder,
    upsert_record,
)
from app.services.xiaohongshu import XhsError, fetch_note, format_note_text, parse_xhs_ref

# 操作分类（前端目录按 order 排序）
TOOL_CATEGORIES: dict[str, dict[str, Any]] = {
    "library": {"label": "笔记库", "order": 1},
    "folder": {"label": "分类", "order": 2},
    "extract": {"label": "提取", "order": 3},
    "manage": {"label": "管理", "order": 4},
}

_TOOL_META: dict[str, dict[str, str]] = {
    "list_records": {"category": "library", "label": "列出笔记"},
    "get_record": {"category": "library", "label": "读取笔记详情"},
    "list_folders": {"category": "folder", "label": "列出文件夹"},
    "create_folder": {"category": "folder", "label": "新建文件夹"},
    "move_records": {"category": "folder", "label": "移动笔记到文件夹"},
    "extract_note": {"category": "extract", "label": "从链接提取笔记"},
    "delete_records": {"category": "manage", "label": "删除笔记"},
    "export_records": {"category": "manage", "label": "导出笔记"},
}


def tool_category(name: str) -> str:
    return _TOOL_META.get(name, {}).get("category") or "library"


def tool_label(name: str) -> str:
    return _TOOL_META.get(name, {}).get("label") or name


def _record_id(args: dict[str, Any]) -> str:
    """笔记 id，与存储字段 record.id / list_records.id 一致。"""
    return str(args.get("id") or args.get("record_id") or "").strip()


def _record_ids(args: dict[str, Any]) -> list[str]:
    """笔记 id 列表，兼容旧参数 record_ids。"""
    raw: Any = args.get("ids")
    if raw is None:
        raw = args.get("record_ids")
    if raw is None and args.get("id"):
        raw = [args.get("id")]
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _folder_id_by_name(name: str) -> str | None:
    key = (name or "").strip().lower()
    if not key:
        return None
    for folder in list_user_folders():
        if (folder.get("name") or "").strip().lower() == key:
            return folder.get("id")
    return None


def _resolve_folder_target(args: dict[str, Any]) -> tuple[str | None, str | None]:
    """
    解析目标文件夹，与 folder 存储字段对齐。
    返回 (folder_id | None 表示未分类, error)。
    """
    if args.get("folder_name"):
        fid = _folder_id_by_name(str(args["folder_name"]))
        if not fid:
            return None, f"文件夹不存在: {args['folder_name']}"
        return fid, None
    folder_id = args.get("folder_id")
    if folder_id is None or folder_id == "":
        return None, None
    fid = str(folder_id).strip()
    if is_uncategorized_folder_id(fid):
        return None, None
    if get_folder(fid):
        return fid, None
    return None, f"文件夹不存在: {fid}"


def get_openai_tools(*, intent: str | None = None) -> list[dict[str, Any]]:
    """返回 OpenAI tools；write 分类仅暴露 folder 变更工具，避免误调 get_record。"""
    specs: list[tuple[str, str, dict[str, Any]]] = [
        (
            "list_records",
            "列出本地笔记库摘要，可按关键词过滤标题。",
            {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "可选，标题关键词（不区分大小写）"},
                    "limit": {
                        "type": "integer",
                        "description": "最多返回条数，默认 30，最大 100",
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "additionalProperties": False,
            },
        ),
        (
            "get_record",
            "读取单条笔记详情（含正文 text）。参数 id 同 list_records 返回的 id。",
            {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "笔记 id（同 records[].id）"},
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        ),
        (
            "list_folders",
            "列出所有文件夹（含 parent_id）。",
            {"type": "object", "properties": {}, "additionalProperties": False},
        ),
        (
            "create_folder",
            "新建文件夹，可指定父文件夹。",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "文件夹名称"},
                    "parent_id": {"type": "string", "description": "父文件夹 id，省略则为顶级"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        ),
        (
            "move_records",
            "批量移动笔记；folder_id 同 folders[].id，folder_name 同 folders[].name；二者皆空表示未分类。",
            {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "笔记 id 列表（同 records[].id）",
                    },
                    "folder_id": {
                        "type": ["string", "null"],
                        "description": "目标文件夹 id（同 folders[].id），null=未分类",
                    },
                    "folder_name": {
                        "type": "string",
                        "description": "目标文件夹名称（同 folders[].name），与 folder_id 二选一",
                    },
                },
                "required": ["ids"],
                "additionalProperties": False,
            },
        ),
        (
            "extract_note",
            "从 B 站或小红书链接提取笔记并保存到本地库。",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "视频/笔记链接"},
                    "page": {"type": "integer", "description": "B 站分 P，默认 1", "minimum": 1},
                    "force": {"type": "boolean", "description": "true 时忽略去重重拉"},
                    "folder_id": {"type": "string", "description": "保存到文件夹 id（同 folders[].id）"},
                    "folder_name": {"type": "string", "description": "保存到文件夹名称（同 folders[].name）"},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        ),
        (
            "delete_records",
            "批量删除本地笔记（不可恢复）。",
            {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "笔记 id 列表（同 records[].id）",
                    },
                },
                "required": ["ids"],
                "additionalProperties": False,
            },
        ),
        (
            "export_records",
            "批量导出笔记正文为 txt 或 json。",
            {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "笔记 id 列表（同 records[].id）",
                    },
                    "format": {"type": "string", "enum": ["txt", "json"], "description": "导出格式"},
                },
                "required": ["ids"],
                "additionalProperties": False,
            },
        ),
    ]
    all_tools = [
        {
            "type": "function",
            "function": {"name": name, "description": desc, "parameters": params},
        }
        for name, desc, params in specs
    ]
    if intent == "write":
        # ponytail: 分类 mutate 预分析已含 id/folder_id，勿再 list/get 正文
        allowed = {"list_folders", "create_folder", "move_records"}
        return [t for t in all_tools if t["function"]["name"] in allowed]
    if intent == "query":
        allowed = {"list_folders", "list_records", "get_record"}
        return [t for t in all_tools if t["function"]["name"] in allowed]
    return all_tools


def execute(name: str, arguments: dict[str, Any]) -> str:
    handlers = {
        "list_records": _list_records,
        "get_record": _get_record,
        "list_folders": _list_folders,
        "create_folder": _create_folder,
        "move_records": _move_records,
        "extract_note": _extract_note,
        "delete_records": _delete_records,
        "export_records": _export_records,
    }
    fn = handlers.get(name)
    if not fn:
        return json.dumps({"ok": False, "error": f"未知工具: {name}"}, ensure_ascii=False)
    try:
        return fn(arguments or {})
    except Exception as err:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False)


def _list_records(args: dict[str, Any]) -> str:
    keyword = str(args.get("keyword") or "").strip().lower()
    limit = min(max(int(args.get("limit") or 30), 1), 100)
    items = list_records()
    if keyword:
        items = [x for x in items if keyword in (x.get("title") or "").lower()]
    items = items[:limit]
    return json.dumps({"ok": True, "count": len(items), "records": items}, ensure_ascii=False)


def _get_record(args: dict[str, Any]) -> str:
    rid = _record_id(args)
    if not rid:
        return json.dumps({"ok": False, "error": "缺少 id"}, ensure_ascii=False)
    rec = get_record(rid)
    if not rec:
        return json.dumps({"ok": False, "error": f"笔记不存在: {rid}"}, ensure_ascii=False)
    text = rec.get("text") or ""
    if len(text) > 12000:
        rec = {**rec, "text": text[:12000] + "\n…（已截断）"}
    return json.dumps({"ok": True, "record": rec}, ensure_ascii=False)


def _list_folders(_args: dict[str, Any]) -> str:
    folders = list_user_folders()
    return json.dumps({"ok": True, "count": len(folders), "folders": folders}, ensure_ascii=False)


def _create_folder(args: dict[str, Any]) -> str:
    name = str(args.get("name") or "").strip()
    if not name:
        return json.dumps({"ok": False, "error": "文件夹名称不能为空"}, ensure_ascii=False)
    parent_id = args.get("parent_id")
    if parent_id is not None:
        parent_id = str(parent_id).strip() or None
        if parent_id and is_system_folder(parent_id):
            return json.dumps({"ok": False, "error": "不能在系统文件夹下创建子文件夹"}, ensure_ascii=False)
        if parent_id and not get_folder(parent_id):
            return json.dumps({"ok": False, "error": f"父文件夹不存在: {parent_id}"}, ensure_ascii=False)
    folder = create_folder(name, parent_id)
    return json.dumps({"ok": True, "folder": folder}, ensure_ascii=False)


def _move_records(args: dict[str, Any]) -> str:
    ids = _record_ids(args)
    if not ids:
        return json.dumps({"ok": False, "error": "ids 不能为空"}, ensure_ascii=False)
    folder_id, err = _resolve_folder_target(args)
    if err:
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)
    result = move_records_to_folder(ids, folder_id)
    return json.dumps({"ok": True, **result}, ensure_ascii=False)


def _find_existing_bilibili(url: str, page: int, lang: str | None) -> dict[str, Any] | None:
    try:
        ref = parse_bilibili_ref(url)
    except BilibiliError:
        return None
    bvid = ref.bvid
    if not bvid:
        return None
    if lang:
        return find_by_dedupe_key(bvid, page, lang)
    records = find_by_bvid_page(bvid, page)
    if not records:
        return None
    for prefer in ("zh-cn", "zh", "ai-zh", "ai_zh"):
        for rec in records:
            lan = ((rec.get("selected_track") or {}).get("lan") or "").lower()
            if lan == prefer:
                return rec
    return records[0]


def _find_existing_xhs(url: str) -> dict[str, Any] | None:
    try:
        ref = parse_xhs_ref(url)
    except XhsError:
        return None
    return find_by_xhs_note_id(ref.note_id)


def _extract_note(args: dict[str, Any]) -> str:
    url = str(args.get("url") or "").strip()
    if not url:
        return json.dumps({"ok": False, "error": "缺少 url"}, ensure_ascii=False)
    page = max(int(args.get("page") or 1), 1)
    force = bool(args.get("force"))
    folder_id, err = _resolve_folder_target(args)
    if err:
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    try:
        platform = detect_platform(url)
    except ValueError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    if not force:
        existing = (
            _find_existing_xhs(url)
            if platform == "xiaohongshu"
            else _find_existing_bilibili(url, page, None)
        )
        if existing:
            return json.dumps(
                {
                    "ok": True,
                    "duplicate": True,
                    "id": existing.get("id"),
                    "title": existing.get("title"),
                    "source": infer_source(existing),
                },
                ensure_ascii=False,
            )

    try:
        if platform == "xiaohongshu":
            result = fetch_note(url)
            payload = {
                "source": "xiaohongshu",
                "source_url": url,
                "note_id": result.note_id,
                "note_type": result.note_type,
                "author": result.author,
                "tags": list(result.tags),
                "images": list(result.images),
                "title": result.title,
                "page": 1,
                "page_title": result.note_type,
                "text": format_note_text(title=result.title, desc=result.desc, tags=result.tags),
            }
        else:
            result = fetch_subtitles(url, page=page, lang=None)
            track = result.selected or {}
            payload = {
                "source": "bilibili",
                "source_url": url,
                "bvid": result.bvid,
                "aid": result.aid,
                "cid": result.cid,
                "title": result.title,
                "page": result.page,
                "page_title": result.page_title,
                "selected_track": track,
                "lines": result.lines,
                "text": format_subtitle_text(result.lines),
            }
    except (BilibiliError, XhsError) as exc:
        return json.dumps(
            {"ok": False, "error": str(exc), "need_login": exc.need_login},
            ensure_ascii=False,
        )

    if folder_id is not None:
        payload["folder_id"] = folder_id
    saved = upsert_record(payload)
    return json.dumps(
        {
            "ok": True,
            "duplicate": False,
            "id": saved.get("id"),
            "title": saved.get("title"),
            "source": infer_source(saved),
        },
        ensure_ascii=False,
    )


def _delete_records(args: dict[str, Any]) -> str:
    ids = _record_ids(args)
    if not ids:
        return json.dumps({"ok": False, "error": "ids 不能为空"}, ensure_ascii=False)
    result = delete_records(ids)
    return json.dumps({"ok": True, **result}, ensure_ascii=False)


def _export_records(args: dict[str, Any]) -> str:
    ids = _record_ids(args)
    if not ids:
        return json.dumps({"ok": False, "error": "ids 不能为空"}, ensure_ascii=False)
    fmt = str(args.get("format") or "txt").strip().lower()
    if fmt not in ("txt", "json"):
        fmt = "txt"
    result = export_records(ids, fmt)
    content = result.get("content") or ""
    if len(content) > 8000:
        result = {**result, "content": content[:8000] + "\n…（已截断）", "truncated": True}
    return json.dumps({"ok": True, **result}, ensure_ascii=False)


if __name__ == "__main__":
    assert tool_category("list_records") == "library"
    assert tool_label("extract_note") == "从链接提取笔记"
    assert len(get_openai_tools()) == len(_TOOL_META)
    assert _record_ids({"ids": ["a"]}) == ["a"]
    assert _record_ids({"record_ids": ["b"]}) == ["b"]
    assert _record_id({"id": "c"}) == "c"
    print("chat_tools self-check ok")
