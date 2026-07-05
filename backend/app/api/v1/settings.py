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
    if "bilibili_sessdata" in updates:
        val = updates["bilibili_sessdata"]
        settings_store.patch_settings({"bilibili_sessdata": (val or "").strip()})
    return SettingsPublic.model_validate(settings_store.public_settings())
