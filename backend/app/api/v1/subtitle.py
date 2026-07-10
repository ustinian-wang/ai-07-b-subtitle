from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    BatchDeleteResponse,
    BatchExportRequest,
    BatchExportResponse,
    BatchIdsRequest,
    BatchMoveRequest,
    BatchMoveResponse,
    FolderCreateRequest,
    FolderPublic,
    FolderUpdateRequest,
    LibraryTreeResponse,
    NotionSyncFailedItem,
    NotionSyncItem,
    NotionSyncRequest,
    NotionSyncResponse,
    SubtitleExtractRequest,
    SubtitleExtractResponse,
    SubtitleLine,
    SubtitleRecordSummary,
    SubtitleSaveRequest,
    SubtitleTrack,
)
from app.services.bilibili import BilibiliError, fetch_subtitles, format_subtitle_text, parse_bilibili_ref
from app.services.folder_store import (
    create_folder,
    delete_folder,
    descendant_folder_ids,
    get_folder,
    is_system_folder,
    resolve_folder_delete_target,
    update_folder,
)
from app.services.platform import detect_platform
from app.services.notion_sync import batch_sync_records
from app.services import settings_store
from app.services.subtitle_store import (
    build_library_tree,
    delete_records,
    export_records,
    find_by_bvid_page,
    find_by_dedupe_key,
    find_by_xhs_note_id,
    get_record,
    infer_source,
    list_records,
    move_records_on_folder_delete,
    move_records_to_folder,
    upsert_record,
)
from app.services.xiaohongshu import XhsError, fetch_note, format_note_text, parse_xhs_ref

router = APIRouter(prefix="/api/v1/subtitle", tags=["subtitle"])


def _build_bilibili_response(
    result,
    *,
    source_url: str = "",
    record_id: str | None = None,
    duplicate: bool = False,
    existing_record_id: str | None = None,
) -> SubtitleExtractResponse:
    tracks = [
        SubtitleTrack(id=t.get("id"), lan=t.get("lan") or "", lan_doc=t.get("lan_doc") or "")
        for t in result.tracks
    ]
    selected = None
    if result.selected:
        s = result.selected
        selected = SubtitleTrack(id=s.get("id"), lan=s.get("lan") or "", lan_doc=s.get("lan_doc") or "")

    lines = [
        SubtitleLine.model_validate(
            {"from": row.get("from", 0), "to": row.get("to", 0), "content": row.get("content") or ""}
        )
        for row in result.lines
    ]

    return SubtitleExtractResponse(
        source="bilibili",
        bvid=result.bvid,
        aid=result.aid,
        cid=result.cid,
        title=result.title,
        page=result.page,
        page_title=result.page_title,
        tracks=tracks,
        selected_track=selected,
        lines=lines,
        text=format_subtitle_text(result.lines),
        need_login=result.need_login,
        hint=result.hint,
        record_id=record_id,
        source_url=source_url,
        duplicate=duplicate,
        existing_record_id=existing_record_id,
    )


def _build_xhs_response(
    result,
    *,
    source_url: str = "",
    record_id: str | None = None,
    duplicate: bool = False,
    existing_record_id: str | None = None,
) -> SubtitleExtractResponse:
    return SubtitleExtractResponse(
        source="xiaohongshu",
        note_id=result.note_id,
        note_type=result.note_type,
        author=result.author,
        tags=list(result.tags),
        images=list(result.images),
        title=result.title,
        page=1,
        page_title=result.note_type,
        text=format_note_text(title=result.title, desc=result.desc, tags=result.tags),
        need_login=result.need_login,
        hint=result.hint,
        record_id=record_id,
        source_url=source_url,
        duplicate=duplicate,
        existing_record_id=existing_record_id,
    )


def _response_from_record(
    rec: dict,
    *,
    source_url: str = "",
    duplicate: bool = False,
) -> SubtitleExtractResponse:
    source = infer_source(rec)
    track = rec.get("selected_track")
    selected = SubtitleTrack.model_validate(track) if track else None
    lines = [
        SubtitleLine.model_validate(
            {"from": row.get("from", 0), "to": row.get("to", 0), "content": row.get("content") or ""}
        )
        for row in rec.get("lines") or []
    ]
    rid = rec.get("id")
    return SubtitleExtractResponse(
        source=source,
        bvid=rec.get("bvid") or "",
        aid=int(rec.get("aid") or 0),
        cid=int(rec.get("cid") or 0),
        note_id=rec.get("note_id") or "",
        note_type=rec.get("note_type") or "",
        author=rec.get("author") or "",
        tags=list(rec.get("tags") or []),
        images=list(rec.get("images") or []),
        title=rec.get("title") or "",
        page=int(rec.get("page") or 1),
        page_title=rec.get("page_title") or "",
        tracks=[selected] if selected else [],
        selected_track=selected,
        lines=lines,
        text=rec.get("text") or "",
        record_id=rid,
        source_url=source_url or rec.get("source_url") or "",
        duplicate=duplicate,
        existing_record_id=rid if duplicate else None,
    )


def _payload_from_response(body: SubtitleSaveRequest | SubtitleExtractResponse) -> dict:
    track = body.selected_track.model_dump() if body.selected_track else None
    lines = [ln.model_dump(by_alias=True) for ln in body.lines]
    return {
        "source": getattr(body, "source", "bilibili") or "bilibili",
        "source_url": getattr(body, "source_url", "") or "",
        "bvid": body.bvid,
        "aid": body.aid,
        "cid": body.cid,
        "note_id": getattr(body, "note_id", "") or "",
        "note_type": getattr(body, "note_type", "") or "",
        "author": getattr(body, "author", "") or "",
        "tags": list(getattr(body, "tags", []) or []),
        "images": list(getattr(body, "images", []) or []),
        "title": body.title,
        "page": body.page,
        "page_title": body.page_title,
        "selected_track": track,
        "lines": lines,
        "text": body.text,
    }


def _summary_from_saved(saved: dict) -> dict:
    from app.services.subtitle_store import _summary

    return _summary(saved)


def _find_existing_bilibili(url: str, page: int, lang: str | None) -> dict | None:
    try:
        ref = parse_bilibili_ref(url)
    except BilibiliError:
        return None
    bvid = ref.bvid
    if not bvid and ref.aid:
        return None
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


def _find_existing_xhs(url: str) -> dict | None:
    try:
        ref = parse_xhs_ref(url)
    except XhsError:
        return None
    return find_by_xhs_note_id(ref.note_id)


def _find_existing_for_extract(url: str, page: int, lang: str | None) -> dict | None:
    try:
        platform = detect_platform(url)
    except ValueError:
        return None
    if platform == "xiaohongshu":
        return _find_existing_xhs(url)
    return _find_existing_bilibili(url, page, lang)


@router.post("/extract", response_model=SubtitleExtractResponse)
def extract_subtitle(body: SubtitleExtractRequest) -> SubtitleExtractResponse:
    source_url = body.url.strip()

    try:
        platform = detect_platform(source_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not body.force:
        existing = _find_existing_for_extract(source_url, body.page, body.lang)
        if existing:
            return _response_from_record(existing, source_url=source_url, duplicate=True)

    try:
        if platform == "xiaohongshu":
            result = fetch_note(source_url)
            resp = _build_xhs_response(result, source_url=source_url)
        else:
            result = fetch_subtitles(source_url, page=body.page, lang=body.lang)
            resp = _build_bilibili_response(result, source_url=source_url)
    except (BilibiliError, XhsError) as exc:
        status = 401 if exc.need_login else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    payload = _payload_from_response(resp)
    if body.folder_id is not None or body.force:
        payload["folder_id"] = body.folder_id
    saved = upsert_record(payload)
    resp.record_id = saved["id"]

    return resp


@router.post("/save", response_model=SubtitleRecordSummary)
def save_subtitle(body: SubtitleSaveRequest) -> SubtitleRecordSummary:
    saved = upsert_record(_payload_from_response(body))
    return SubtitleRecordSummary.model_validate(_summary_from_saved(saved))


@router.get("/records", response_model=list[SubtitleRecordSummary])
def list_subtitle_records() -> list[SubtitleRecordSummary]:
    return [SubtitleRecordSummary.model_validate(x) for x in list_records()]


@router.get("/tree", response_model=LibraryTreeResponse)
def get_library_tree() -> LibraryTreeResponse:
    return LibraryTreeResponse.model_validate(build_library_tree())


@router.post("/folders", response_model=FolderPublic)
def create_subtitle_folder(body: FolderCreateRequest) -> FolderPublic:
    try:
        if body.parent_id and not get_folder(body.parent_id):
            raise HTTPException(status_code=400, detail="父文件夹不存在")
        return FolderPublic.model_validate(create_folder(body.name, body.parent_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/folders/{folder_id}", response_model=FolderPublic)
def update_subtitle_folder(folder_id: str, body: FolderUpdateRequest) -> FolderPublic:
    if is_system_folder(folder_id):
        raise HTTPException(status_code=400, detail="系统文件夹不可修改")
    if not get_folder(folder_id):
        raise HTTPException(status_code=404, detail="文件夹不存在")
    try:
        kwargs: dict = {}
        if body.name is not None:
            kwargs["name"] = body.name
        if "parent_id" in body.model_fields_set:
            kwargs["parent_id"] = body.parent_id
        return FolderPublic.model_validate(update_folder(folder_id, **kwargs))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/folders/{folder_id}")
def remove_subtitle_folder(folder_id: str) -> dict:
    if is_system_folder(folder_id):
        raise HTTPException(status_code=400, detail="系统文件夹不可删除")
    item = get_folder(folder_id)
    if not item:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    parent_id = item.get("parent_id")
    target_id = resolve_folder_delete_target(parent_id)
    removed_ids = {folder_id, *descendant_folder_ids(folder_id)}
    for fid in removed_ids:
        move_records_on_folder_delete(fid, target_id)
    try:
        result = delete_folder(folder_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.post("/records/batch-move", response_model=BatchMoveResponse)
def batch_move_records(body: BatchMoveRequest) -> BatchMoveResponse:
    from app.services.folder_store import is_uncategorized_folder_id

    if body.folder_id and not is_uncategorized_folder_id(body.folder_id) and not get_folder(body.folder_id):
        raise HTTPException(status_code=400, detail="目标文件夹不存在")
    result = move_records_to_folder(body.ids, body.folder_id)
    return BatchMoveResponse(
        ok=not result["failed"] or bool(result["moved"]),
        moved=result["moved"],
        failed=result["failed"],
    )


@router.get("/records/{record_id}", response_model=SubtitleExtractResponse)
def get_subtitle_record(record_id: str) -> SubtitleExtractResponse:
    rec = get_record(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _response_from_record(rec)


@router.delete("/records/{record_id}")
def remove_subtitle_record(record_id: str) -> dict:
    result = delete_records([record_id])
    if record_id in result["failed"]:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True, "id": record_id}


@router.post("/records/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_records(body: BatchIdsRequest) -> BatchDeleteResponse:
    result = delete_records(body.ids)
    return BatchDeleteResponse(
        ok=not result["failed"] or bool(result["deleted"]),
        deleted=result["deleted"],
        failed=result["failed"],
    )


@router.post("/records/batch-export", response_model=BatchExportResponse)
def batch_export_records(body: BatchExportRequest) -> BatchExportResponse:
    result = export_records(body.ids, fmt=body.format)
    return BatchExportResponse.model_validate(result)


@router.post("/records/batch-sync-notion", response_model=NotionSyncResponse)
def batch_sync_notion(body: NotionSyncRequest) -> NotionSyncResponse:
    if not settings_store.notion_configured():
        raise HTTPException(
            status_code=400,
            detail="Notion 未配置，请前往设置页填写 Integration Token 与父页面 ID",
        )
    result = batch_sync_records(body.ids)
    return NotionSyncResponse(
        ok=not result["failed"] or bool(result["synced"]),
        synced=[NotionSyncItem.model_validate(x) for x in result["synced"]],
        failed=[NotionSyncFailedItem.model_validate(x) for x in result["failed"]],
    )


def _api_self_check() -> None:
    """ponytail: TestClient 冒烟，不调用 B 站 / 小红书外网。"""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.subtitle_store import upsert_record

    client = TestClient(app)
    assert client.get("/api/health").json()["ok"] is True

    rid = upsert_record(
        {
            "source_url": "https://example.com/v",
            "source": "bilibili",
            "bvid": "BV1test00001",
            "aid": 1,
            "cid": 2,
            "title": "API自检",
            "page": 1,
            "selected_track": {"lan": "ai-zh", "lan_doc": "AI中文"},
            "lines": [{"from": 0, "to": 1, "content": "line"}],
            "text": "[00:00.00] line",
        }
    )["id"]

    dup = client.post(
        "/api/v1/subtitle/extract",
        json={"url": "https://www.bilibili.com/video/BV1test00001", "page": 1},
    )
    assert dup.status_code == 200
    body = dup.json()
    assert body["duplicate"] is True
    assert body["existing_record_id"] == rid

    xhs_id = "656abc123def456789012346"
    xhs_rid = upsert_record(
        {
            "source": "xiaohongshu",
            "note_id": xhs_id,
            "title": "小红书API自检",
            "note_type": "normal",
            "tags": ["测试"],
            "text": "正文",
            "source_url": f"https://www.xiaohongshu.com/explore/{xhs_id}",
        }
    )["id"]
    xhs_dup = client.post(
        "/api/v1/subtitle/extract",
        json={"url": f"https://www.xiaohongshu.com/explore/{xhs_id}"},
    )
    assert xhs_dup.status_code == 200
    assert xhs_dup.json()["duplicate"] is True

    tree = client.get("/api/v1/subtitle/tree")
    assert tree.status_code == 200
    assert tree.json()["total_count"] >= 2

    sys_del = client.delete("/api/v1/subtitle/folders/__uncategorized__")
    assert sys_del.status_code == 400

    folder = client.post("/api/v1/subtitle/folders", json={"name": "API测试夹"})
    assert folder.status_code == 200
    fid = folder.json()["id"]
    moved = client.post(
        "/api/v1/subtitle/records/batch-move",
        json={"ids": [rid], "folder_id": fid},
    )
    assert moved.status_code == 200
    assert rid in moved.json()["moved"]

    client.delete(f"/api/v1/subtitle/folders/{fid}")

    exported = client.post(
        "/api/v1/subtitle/records/batch-export",
        json={"ids": [rid], "format": "txt"},
    )
    assert exported.status_code == 200
    assert "line" in exported.json()["content"]

    deleted = client.post(
        "/api/v1/subtitle/records/batch-delete",
        json={"ids": [rid, xhs_rid]},
    )
    assert deleted.status_code == 200
    assert rid in deleted.json()["deleted"]


if __name__ == "__main__":
    _api_self_check()
    print("subtitle API self-check ok")
