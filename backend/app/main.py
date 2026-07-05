from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_settings, settings

app = FastAPI(title="ai sandbox", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    load_settings()
    return {
        "ok": True,
        "project": "ai-07-b-subtitle",
        "backend_port": settings.backend_port,
    }


if __name__ == "__main__":
    import uvicorn

    load_settings()
    port = int(os.getenv("PORT", os.getenv("BACKEND_PORT", str(settings.backend_port))))
    host = os.getenv("BACKEND_HOST", settings.backend_host).strip() or "127.0.0.1"
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
