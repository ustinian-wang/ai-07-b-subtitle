from __future__ import annotations

from pydantic import BaseModel, Field


class SubtitleExtractRequest(BaseModel):
    url: str = Field(..., min_length=4, description="B 站视频链接或 BV/av 号")
    page: int = Field(1, ge=1, description="分 P 序号，从 1 开始")
    lang: str | None = Field(None, description="优先字幕语言，如 zh-CN / ai-zh")
    save: bool = Field(True, description="提取成功后自动保存到本地库")
    force: bool = Field(False, description="强制重新提取，忽略本地已有记录")
    folder_id: str | None = Field(None, description="保存到指定文件夹，null 为未分类")


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
    duplicate: bool = False
    existing_record_id: str | None = None


class SubtitleRecordSummary(BaseModel):
    id: str
    folder_id: str | None = None
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


class BatchIdsRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1)


class BatchExportRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1)
    format: str = Field("txt", pattern="^(txt|json)$", description="导出格式：txt 或 json")


class BatchExportResponse(BaseModel):
    format: str
    content: str
    filename: str
    count: int = 0
    missing: list[str] = []


class BatchDeleteResponse(BaseModel):
    ok: bool = True
    deleted: list[str] = []
    failed: list[str] = []


class FolderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    parent_id: str | None = None


class FolderUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    parent_id: str | None = None


class FolderPublic(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    created_at: str = ""
    updated_at: str = ""


class LibraryTreeFolder(BaseModel):
    type: str = "folder"
    id: str
    name: str
    parent_id: str | None = None
    children: list["LibraryTreeFolder"] = []
    records: list[SubtitleRecordSummary] = []


class LibraryTreeResponse(BaseModel):
    folders: list[LibraryTreeFolder]
    uncategorized: list[SubtitleRecordSummary]
    total_count: int = 0


class BatchMoveRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1)
    folder_id: str | None = Field(None, description="目标文件夹，null 为未分类")


class BatchMoveResponse(BaseModel):
    ok: bool = True
    moved: list[str] = []
    failed: list[str] = []


LibraryTreeFolder.model_rebuild()


class SettingsPublic(BaseModel):
    bilibili_sessdata_configured: bool = False
    bilibili_sessdata_masked: str = ""


class SettingsPatchRequest(BaseModel):
    bilibili_sessdata: str | None = None
