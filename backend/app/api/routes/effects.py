"""Audio effects preview and custom preset routes."""

import base64
import os
import tempfile
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.audio.effects import (
    apply_effects, EFFECT_PRESETS, get_all_presets,
    load_custom_presets, save_custom_preset, delete_custom_preset,
)
from app.schemas import EffectPreviewRequest

router = APIRouter(prefix="/effects", tags=["effects"])


PRESET_DESCRIPTIONS = {
    "radio": "Military/aviation radio comms",
    "helmet": "Muffled helmet comms with echo",
    "robot": "Synthetic robotic voice",
    "telephone": "Old landline telephone quality",
    "megaphone": "Loud, overdriven megaphone",
    "vhs": "Warm, degraded VHS tape",
    "corrupted_ai": "Glitchy, broken AI voice",
    "deep_space": "Distant, echoing space transmission",
    "glitch": "Heavy digital artifacts",
    "alien": "Pitch-shifted otherworldly voice",
    "whisper": "Hushed, intimate whisper",
    "underwater": "Submerged, muffled underwater",
    "demonic": "Deep, ominous demonic voice",
}


@router.get("/presets")
async def list_presets():
    """List all audio effect presets (built-in + custom)."""
    custom = load_custom_presets()
    all_presets = get_all_presets()
    return {
        "presets": list(all_presets.keys()),
        "built_in": list(EFFECT_PRESETS.keys()),
        "custom": list(custom.keys()),
        "descriptions": PRESET_DESCRIPTIONS,
    }


class CustomPresetCreate(BaseModel):
    name: str
    filter_chain: str
    description: str = ""


@router.get("/custom")
async def list_custom_presets():
    """List user-defined custom effects."""
    return load_custom_presets()


@router.post("/custom")
async def create_custom_preset(body: CustomPresetCreate):
    """Add or update a custom audio effect preset.

    filter_chain is a comma-separated FFmpeg filter string, e.g.:
       'highpass=f=300,lowpass=f=3400,volume=1.2'

    Filter reference: https://ffmpeg.org/ffmpeg-filters.html#Audio-Filters
    """
    name = body.name.lower().strip().replace(" ", "_")
    if not name:
        raise HTTPException(400, "Name cannot be empty")
    if name in EFFECT_PRESETS:
        raise HTTPException(400, f"'{name}' is a built-in preset and cannot be overridden")
    save_custom_preset(name, body.filter_chain)
    return {"name": name, "filter_chain": body.filter_chain}


@router.delete("/custom/{name}")
async def remove_custom_preset(name: str):
    """Delete a custom preset by name."""
    if delete_custom_preset(name):
        return {"deleted": name}
    raise HTTPException(404, f"Custom preset '{name}' not found")


@router.post("/preview")
async def preview_effect(req: EffectPreviewRequest):
    """Apply an effect to audio and return the result as base64."""
    all_presets = get_all_presets()
    if req.preset not in all_presets and req.preset != "none":
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
