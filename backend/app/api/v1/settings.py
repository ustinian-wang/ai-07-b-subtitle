from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import SettingsPatchRequest, SettingsPublic
from app.services import settings_store

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=SettingsPublic)
def get_settings() -> SettingsPublic:
    return SettingsPublic.model_validate(settings_store.public_settings())


@router.patch("", response_model=SettingsPublic)
def patch_settings(body: SettingsPatchRequest) -> SettingsPublic:
    updates = body.model_dump(exclude_unset=True)
    patch: dict = {}
    if "bilibili_sessdata" in updates:
        patch["bilibili_sessdata"] = (updates["bilibili_sessdata"] or "").strip()
    if "xiaohongshu_cookie" in updates:
        patch["xiaohongshu_cookie"] = (updates["xiaohongshu_cookie"] or "").strip()
    if "openai_api_key" in updates:
        patch["openai_api_key"] = (updates["openai_api_key"] or "").strip()
    if "openai_base_url" in updates:
        patch["openai_base_url"] = (updates["openai_base_url"] or "").strip()
    if "openai_model" in updates:
        patch["openai_model"] = (updates["openai_model"] or "").strip()
    if "notion_token" in updates:
        patch["notion_token"] = (updates["notion_token"] or "").strip()
    if "notion_parent_id" in updates:
        patch["notion_parent_id"] = (updates["notion_parent_id"] or "").strip()
    if patch:
        settings_store.patch_settings(patch)
    return SettingsPublic.model_validate(settings_store.public_settings())
