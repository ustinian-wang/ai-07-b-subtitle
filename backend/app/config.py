"""加载 backend/.env 与简单配置。"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def load_settings() -> None:
    load_dotenv(BACKEND_ROOT / ".env", override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    backend_port: int = 8805
    backend_host: str = "127.0.0.1"


load_settings()
settings = Settings()
