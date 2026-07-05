from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    BatchDeleteResponse,
    BatchExportRequest,
    BatchExportResponse,
    BatchIdsRequest,
    SubtitleExtractRequest,
    SubtitleExtractResponse,
    SubtitleLine,
    SubtitleRecordSummary,
    SubtitleSaveRequest,
    SubtitleTrack,
)
from app.services.bilibili import BilibiliError, fetch_subtitles, format_subtitle_text, parse_bilibili_ref
from app.services.subtitle_store import (
    delete_records,
    export_records,
    find_by_bvid_page,
    find_by_dedupe_key,
    get_record,
    list_records,
    upsert_record,
)

router = APIRouter(prefix="/api/v1/subtitle", tags=["subtitle"])


def _build_response(
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


def _response_from_record(
    rec: dict,
    *,
    source_url: str = "",
    duplicate: bool = False,
) -> SubtitleExtractResponse:
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
        bvid=rec.get("bvid") or "",
        aid=int(rec.get("aid") or 0),
        cid=int(rec.get("cid") or 0),
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
        "source_url": getattr(body, "source_url", "") or "",
        "bvid": body.bvid,
        "aid": body.aid,
        "cid": body.cid,
        "title": body.title,
        "page": body.page,
        "page_title": body.page_title,
        "selected_track": track,
        "lines": lines,
        "text": body.text,
    }


def _find_existing_for_extract(url: str, page: int, lang: str | None) -> dict | None:
    try:
        ref = parse_bilibili_ref(url)
    except BilibiliError:
        return None
    bvid = ref.bvid
    if not bvid and ref.aid:
        # ponytail: aid-only 链接无法本地去重，需走 B 站 API 解析 bvid
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


@router.post("/extract", response_model=SubtitleExtractResponse)
def extract_subtitle(body: SubtitleExtractRequest) -> SubtitleExtractResponse:
    source_url = body.url.strip()

    if not body.force:
        existing = _find_existing_for_extract(source_url, body.page, body.lang)
        if existing:
            return _response_from_record(
                existing,
                source_url=source_url,
                duplicate=True,
            )

    try:
        result = fetch_subtitles(body.url, page=body.page, lang=body.lang)
    except BilibiliError as exc:
        status = 401 if exc.need_login else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    resp = _build_response(result, source_url=source_url)

    # ponytail: 提取成功即落盘，与前端「自动保存」一致
    saved = upsert_record(_payload_from_response(resp))
    resp.record_id = saved["id"]

    return resp


@router.post("/save", response_model=SubtitleRecordSummary)
def save_subtitle(body: SubtitleSaveRequest) -> SubtitleRecordSummary:
    saved = upsert_record(_payload_from_response(body))
    return SubtitleRecordSummary.model_validate(
        {
            "id": saved["id"],
            "bvid": saved["bvid"],
            "title": saved["title"],
            "page": saved["page"],
            "page_title": saved["page_title"],
            "line_count": saved["line_count"],
            "lan_doc": (saved.get("selected_track") or {}).get("lan_doc")
            or (saved.get("selected_track") or {}).get("lan")
            or "",
            "source_url": saved.get("source_url") or "",
            "created_at": saved.get("created_at") or "",
            "updated_at": saved.get("updated_at") or "",
        }
    )


@router.get("/records", response_model=list[SubtitleRecordSummary])
def list_subtitle_records() -> list[SubtitleRecordSummary]:
    return [SubtitleRecordSummary.model_validate(x) for x in list_records()]


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


def _api_self_check() -> None:
    """ponytail: TestClient 冒烟，不调用 B 站外网。"""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.subtitle_store import upsert_record

    client = TestClient(app)
    assert client.get("/api/health").json()["ok"] is True

    rid = upsert_record(
        {
            "source_url": "https://example.com/v",
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
        json={"url": "https://www.bilibili.com/video/BV1test00001", "page": 1, "save": False},
    )
    assert dup.status_code == 200
    body = dup.json()
    assert body["duplicate"] is True
    assert body["existing_record_id"] == rid

    exported = client.post(
        "/api/v1/subtitle/records/batch-export",
        json={"ids": [rid], "format": "txt"},
    )
    assert exported.status_code == 200
    assert "line" in exported.json()["content"]

    deleted = client.post(
        "/api/v1/subtitle/records/batch-delete",
        json={"ids": [rid]},
    )
    assert deleted.status_code == 200
    assert rid in deleted.json()["deleted"]


if __name__ == "__main__":
    _api_self_check()
    print("subtitle API self-check ok")
