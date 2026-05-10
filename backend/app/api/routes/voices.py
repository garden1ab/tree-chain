"""Voice and model management routes."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.database import CharacterVoiceConfig, StoredApiKey
from app.core.security import encrypt_api_key, decrypt_api_key
from app.schemas import (
    VoiceInfo, VoiceListResponse, CharacterVoiceConfigSchema,
    CharacterVoiceConfigUpdate, ApiKeyCreate, ApiKeyResponse, ApiKeyValidation,
)
from app.services.elevenlabs import ElevenLabsService, ElevenLabsError

router = APIRouter(prefix="/voices", tags=["voices"])


async def _get_api_key(db: AsyncSession) -> str:
    """Get the active API key from database or environment."""
    from app.core.config import get_settings
    settings = get_settings()

    result = await db.execute(
        select(StoredApiKey)
        .where(StoredApiKey.is_active == True)
        .order_by(StoredApiKey.created_at.desc())
        .limit(1)
    )
    stored = result.scalar_one_or_none()

    if stored:
        return decrypt_api_key(stored.encrypted_key)
    return settings.elevenlabs_api_key


@router.get("/", response_model=VoiceListResponse)
async def list_voices(db: AsyncSession = Depends(get_db)):
    """List available ElevenLabs voices and models."""
    api_key = await _get_api_key(db)
    if not api_key:
        raise HTTPException(400, "No ElevenLabs API key configured")

    service = ElevenLabsService(api_key)
    try:
        voices_raw = await service.list_voices()
        models_raw = await service.list_models()
    except ElevenLabsError as e:
        raise HTTPException(502, str(e))

    voices = [
        VoiceInfo(
            voice_id=v.get("voice_id", ""),
            name=v.get("name", "Unknown"),
            category=v.get("category", ""),
            labels=v.get("labels", {}),
            preview_url=v.get("preview_url", ""),
            description=v.get("description", ""),
        )
        for v in voices_raw
    ]

    return VoiceListResponse(voices=voices, models=models_raw)


@router.post("/sync")
async def sync_voices(db: AsyncSession = Depends(get_db)):
    """Force re-sync of voices from ElevenLabs."""
    return await list_voices(db)


@router.get("/configs/{project_id}")
async def get_character_configs(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get character voice configurations for a project."""
    configs = (await db.execute(
        select(CharacterVoiceConfig).where(CharacterVoiceConfig.project_id == project_id)
    )).scalars().all()

    return [CharacterVoiceConfigSchema.model_validate(c) for c in configs]


@router.put("/configs/{project_id}")
async def update_character_configs(
    project_id: uuid.UUID,
    update: CharacterVoiceConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update character voice configurations for a project."""
    # Remove old configs
    await db.execute(
        delete(CharacterVoiceConfig).where(CharacterVoiceConfig.project_id == project_id)
    )

    # Insert new
    for cfg in update.configs:
        db.add(CharacterVoiceConfig(
            project_id=project_id,
            character_name=cfg.character_name,
            voice_id=cfg.voice_id,
            model_id=cfg.model_id,
            stability=cfg.stability,
            similarity_boost=cfg.similarity_boost,
            style=cfg.style,
            use_speaker_boost=cfg.use_speaker_boost,
            effects_preset=cfg.effects_preset,
            effects_config=cfg.effects_config,
            volume_adjustment=cfg.volume_adjustment,
        ))

    await db.flush()
    return {"status": "ok", "count": len(update.configs)}


# --- API Key Management ---
@router.post("/apikey", response_model=ApiKeyResponse)
async def add_api_key(body: ApiKeyCreate, db: AsyncSession = Depends(get_db)):
    """Store an encrypted ElevenLabs API key, deactivating any previous ones."""
    # Deactivate all existing keys for this provider
    await db.execute(
        update(StoredApiKey)
        .where(StoredApiKey.provider == body.provider, StoredApiKey.is_active == True)
        .values(is_active=False)
    )
    encrypted = encrypt_api_key(body.api_key)
    key = StoredApiKey(
        provider=body.provider,
        label=body.label,
        encrypted_key=encrypted,
        is_active=True,
    )
    db.add(key)
    await db.flush()
    return ApiKeyResponse.model_validate(key)


@router.post("/apikey/validate", response_model=ApiKeyValidation)
async def validate_api_key(body: ApiKeyCreate, db: AsyncSession = Depends(get_db)):
    """Validate an ElevenLabs API key."""
    service = ElevenLabsService(body.api_key)
    try:
        info = await service.get_subscription_info()
        return ApiKeyValidation(
            valid=True,
            message="API key is valid",
            character_count=info.get("character_count"),
            character_limit=info.get("character_limit"),
        )
    except ElevenLabsError as e:
        return ApiKeyValidation(valid=False, message=str(e))


@router.get("/apikeys")
async def list_api_keys(db: AsyncSession = Depends(get_db)):
    """List stored API keys (without revealing actual keys)."""
    keys = (await db.execute(select(StoredApiKey).order_by(StoredApiKey.created_at.desc()))).scalars().all()
    return [ApiKeyResponse.model_validate(k) for k in keys]


@router.delete("/apikey/{key_id}")
async def delete_api_key(key_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a stored API key."""
    await db.execute(delete(StoredApiKey).where(StoredApiKey.id == key_id))
    return {"status": "deleted"}
