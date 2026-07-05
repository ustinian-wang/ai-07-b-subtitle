from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    SubtitleExtractRequest,
    SubtitleExtractResponse,
    SubtitleLine,
    SubtitleRecordSummary,
    SubtitleSaveRequest,
    SubtitleTrack,
)
from app.services.bilibili import BilibiliError, fetch_subtitles, format_subtitle_text
from app.services.subtitle_store import delete_record, get_record, list_records, save_record

router = APIRouter(prefix="/api/v1/subtitle", tags=["subtitle"])


def _build_response(
    result,
    *,
    source_url: str = "",
    record_id: str | None = None,
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


@router.post("/extract", response_model=SubtitleExtractResponse)
def extract_subtitle(body: SubtitleExtractRequest) -> SubtitleExtractResponse:
    try:
        result = fetch_subtitles(body.url, page=body.page, lang=body.lang)
    except BilibiliError as exc:
        status = 401 if exc.need_login else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    source_url = body.url.strip()
    resp = _build_response(result, source_url=source_url)

    if body.save:
        saved = save_record(_payload_from_response(resp))
        resp.record_id = saved["id"]

    return resp


@router.post("/save", response_model=SubtitleRecordSummary)
def save_subtitle(body: SubtitleSaveRequest) -> SubtitleRecordSummary:
    saved = save_record(_payload_from_response(body))
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

    track = rec.get("selected_track")
    selected = SubtitleTrack.model_validate(track) if track else None
    lines = [
        SubtitleLine.model_validate(
            {"from": row.get("from", 0), "to": row.get("to", 0), "content": row.get("content") or ""}
        )
        for row in rec.get("lines") or []
    ]

    return SubtitleExtractResponse(
        bvid=rec.get("bvid") or "",
        aid=int(rec.get("aid") or 0),
        cid=int(rec.get("cid") or 0),
        title=rec.get("title") or "",
        page=int(rec.get("page") or 1),
        page_title=rec.get("page_title") or "",
        tracks=[],
        selected_track=selected,
        lines=lines,
        text=rec.get("text") or "",
        record_id=rec.get("id"),
        source_url=rec.get("source_url") or "",
    )


@router.delete("/records/{record_id}")
def remove_subtitle_record(record_id: str) -> dict:
    if not delete_record(record_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True, "id": record_id}
