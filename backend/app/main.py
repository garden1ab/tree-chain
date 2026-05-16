"""DialogueForge – FastAPI application entry point."""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db import init_db

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# WebSocket connection manager for live logs
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages WebSocket connections for real-time log streaming."""

    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, client_id: str):
        await ws.accept()
        self.active[client_id] = ws

    def disconnect(self, client_id: str):
        self.active.pop(client_id, None)

    async def broadcast(self, message: dict):
        dead = []
        for cid, ws in self.active.items():
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.active.pop(cid, None)


ws_manager = ConnectionManager()

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("dialogueforge.startup", debug=settings.debug)
    await init_db()

    # Auto-import ELEVENLABS_API_KEY from env into database if not already there
    if settings.elevenlabs_api_key:
        try:
            from sqlalchemy import select
            from app.db import async_session
            from app.models.database import StoredApiKey
            from app.core.security import encrypt_api_key
            async with async_session() as db:
                existing = await db.execute(
                    select(StoredApiKey).where(
                        StoredApiKey.provider == "elevenlabs",
                        StoredApiKey.is_active == True,
                    ).limit(1)
                )
                if not existing.scalar_one_or_none():
                    db.add(StoredApiKey(
                        provider="elevenlabs",
                        label="From environment",
                        encrypted_key=encrypt_api_key(settings.elevenlabs_api_key),
                        is_active=True,
                    ))
                    await db.commit()
                    logger.info("Imported ELEVENLABS_API_KEY from environment into database")
        except Exception as e:
            logger.warning("Failed to auto-import API key from env", error=str(e))

    # Register all TTS providers
    from app.services.tts_providers import init_providers
    init_providers()
    yield
    logger.info("dialogueforge.shutdown")

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DialogueForge",
    description="Character dialogue audio generation platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

from app.api.routes import scripts, voices, generation, projects, effects, providers  # noqa: E402

app.include_router(scripts.router, prefix="/api")
app.include_router(voices.router, prefix="/api")
app.include_router(generation.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(effects.router, prefix="/api")
app.include_router(providers.router, prefix="/api")

# ---------------------------------------------------------------------------
# Health & info
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "dialogueforge"}


@app.get("/api/info")
async def info():
    return {
        "name": "DialogueForge",
        "version": "1.0.0",
        "features": [
            "multi-character-dialogue",
            "elevenlabs-tts",
            "audio-effects",
            "smart-caching",
            "project-save-load",
            "cost-estimation",
        ],
    }

# ---------------------------------------------------------------------------
# WebSocket for live logs
# ---------------------------------------------------------------------------

@app.websocket("/api/ws/{client_id}")
async def websocket_endpoint(ws: WebSocket, client_id: str):
    await ws_manager.connect(ws, client_id)
    try:
        while True:
            data = await ws.receive_text()
            # clients can send ping/pong or subscribe to job IDs
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
