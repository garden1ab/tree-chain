"""Audio effects preview routes."""

import base64
import os
import tempfile
from fastapi import APIRouter, HTTPException
from app.audio.effects import apply_effects, EFFECT_PRESETS
from app.schemas import EffectPreviewRequest

router = APIRouter(prefix="/effects", tags=["effects"])


@router.get("/presets")
async def list_presets():
    """List available audio effect presets."""
    return {
        "presets": list(EFFECT_PRESETS.keys()),
        "descriptions": {
            "radio": "Military/aviation radio communication",
            "helmet": "Muffled helmet comms with slight echo",
            "robot": "Synthetic robotic voice processing",
            "telephone": "Old landline telephone quality",
            "megaphone": "Loud, overdriven megaphone",
            "vhs": "Warm, degraded VHS tape quality",
            "corrupted_ai": "Glitchy, broken AI voice",
            "deep_space": "Distant, echoing space transmission",
            "glitch": "Heavy digital artifacts and stuttering",
            "alien": "Pitch-shifted otherworldly voice",
        },
    }


@router.post("/preview")
async def preview_effect(req: EffectPreviewRequest):
    """Apply an effect to audio and return the result as base64."""
    if req.preset not in EFFECT_PRESETS and req.preset != "none":
        raise HTTPException(400, f"Unknown preset: {req.preset}")

    try:
        audio_bytes = base64.b64decode(req.audio_base64)
    except Exception:
        raise HTTPException(400, "Invalid base64 audio data")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as inp:
        inp.write(audio_bytes)
        input_path = inp.name

    output_path = input_path.replace(".wav", "_processed.wav")

    try:
        await apply_effects(input_path, output_path, req.preset, req.config)
        with open(output_path, 'rb') as f:
            result_bytes = f.read()
        return {"audio_base64": base64.b64encode(result_bytes).decode()}
    finally:
        for p in (input_path, output_path):
            if os.path.exists(p):
                os.remove(p)
