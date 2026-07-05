from __future__ import annotations

from pydantic import BaseModel, Field


class SubtitleExtractRequest(BaseModel):
    url: str = Field(..., min_length=4, description="B 站 / 小红书链接")
    page: int = Field(1, ge=1, description="B 站分 P 序号，从 1 开始")
    lang: str | None = Field(None, description="B 站优先字幕语言，如 zh-CN / ai-zh")
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
    source: str = "bilibili"
    bvid: str = ""
    aid: int = 0
    cid: int = 0
    note_id: str = ""
    note_type: str = ""
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    title: str
    page: int = 1
    page_title: str = ""
    tracks: list[SubtitleTrack] = Field(default_factory=list)
    selected_track: SubtitleTrack | None = None
    lines: list[SubtitleLine] = Field(default_factory=list)
    text: str
    need_login: bool = False
    hint: str = ""
    record_id: str | None = None
    source_url: str = ""
    duplicate: bool = False
    existing_record_id: str | None = None


class SubtitleRecordSummary(BaseModel):
    id: str
    source: str = "bilibili"
    folder_id: str | None = None
    bvid: str = ""
    note_id: str = ""
    title: str
    page: int = 1
    page_title: str = ""
    line_count: int = 0
    lan_doc: str = ""
    source_url: str = ""
    created_at: str = ""
    updated_at: str = ""


class SubtitleSaveRequest(BaseModel):
    source: str = "bilibili"
    source_url: str = ""
    bvid: str = ""
    aid: int = 0
    cid: int = 0
    note_id: str = ""
    note_type: str = ""
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    title: str
    page: int = 1
    page_title: str = ""
    selected_track: SubtitleTrack | None = None
    lines: list[SubtitleLine] = Field(default_factory=list)
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
    xiaohongshu_cookie_configured: bool = False
    xiaohongshu_cookie_masked: str = ""


class SettingsPatchRequest(BaseModel):
    bilibili_sessdata: str | None = None
    xiaohongshu_cookie: str | None = None


class ChatRequest(BaseModel):
    thread_id: str = ""
    message: str = Field(..., min_length=1)
    reference_record_ids: list[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatMessagesResponse(BaseModel):
    thread_id: str
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatSessionResponse(BaseModel):
    thread_id: str


class ChatClearResponse(BaseModel):
    ok: bool = True
    thread_id: str = ""
