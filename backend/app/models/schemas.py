from __future__ import annotations

from pydantic import BaseModel, Field


class SubtitleExtractRequest(BaseModel):
    url: str = Field(..., min_length=4, description="B 站视频链接或 BV/av 号")
    page: int = Field(1, ge=1, description="分 P 序号，从 1 开始")
    lang: str | None = Field(None, description="优先字幕语言，如 zh-CN / ai-zh")
    save: bool = Field(False, description="提取成功后自动保存到本地库")


class SubtitleLine(BaseModel):
    from_sec: float = Field(..., alias="from")
    to_sec: float = Field(..., alias="to")
    content: str

    model_config = {"populate_by_name": True}


class SubtitleTrack(BaseModel):
    id: int | str | None = None
    lan: str = ""
    lan_doc: str = ""


class SubtitleExtractResponse(BaseModel):
    bvid: str
    aid: int
    cid: int
    title: str
    page: int
    page_title: str = ""
    tracks: list[SubtitleTrack]
    selected_track: SubtitleTrack | None = None
    lines: list[SubtitleLine]
    text: str
    need_login: bool = False
    hint: str = ""
    record_id: str | None = None
    source_url: str = ""


class SubtitleRecordSummary(BaseModel):
    id: str
    bvid: str
    title: str
    page: int
    page_title: str = ""
    line_count: int = 0
    lan_doc: str = ""
    source_url: str = ""
    created_at: str = ""
    updated_at: str = ""


class SubtitleSaveRequest(BaseModel):
    source_url: str = ""
    bvid: str
    aid: int
    cid: int
    title: str
    page: int = 1
    page_title: str = ""
    selected_track: SubtitleTrack | None = None
    lines: list[SubtitleLine]
    text: str
