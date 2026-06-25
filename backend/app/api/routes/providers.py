"""TTS provider management routes."""

from fastapi import APIRouter, HTTPException

from app.services.tts_providers import list_providers, get_provider

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/")
async def get_providers():
    """List all registered TTS providers."""
    return list_providers()


@router.get("/{provider_name}/voices")
async def get_provider_voices(provider_name: str):
    """List voices available from a specific provider."""
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        raise HTTPException(404, str(e))
    voices = await provider.list_voices()
    return [
        {
            "voice_id": v.voice_id,
            "name": v.name,
            "category": v.category,
            "description": v.description,
        }
        for v in voices
    ]


@router.post("/{provider_name}/validate")
async def validate_provider(provider_name: str):
    """Check if a provider is ready to use."""
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        raise HTTPException(404, str(e))
    valid, message = await provider.validate()
    return {"valid": valid, "message": message, "provider": provider_name}
