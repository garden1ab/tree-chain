"""Chatterbox TTS service — runs as standalone container."""

import io
import os
import torch
import torchaudio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Chatterbox TTS Service")

_model = None


def get_model():
    global _model
    if _model is None:
        from chatterbox.tts import ChatterboxTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading Chatterbox on {device}...")
        _model = ChatterboxTTS.from_pretrained(device=device)
        print("Chatterbox ready.")
    return _model


class GenerateRequest(BaseModel):
    text: str
    voice_id: str = "default"
    exaggeration: float = 0.5
    cfg_weight: float = 0.5


@app.get("/health")
async def health():
    return {"status": "ok", "provider": "chatterbox", "gpu": torch.cuda.is_available()}


@app.get("/voices")
async def list_voices():
    return [
        {"voice_id": "default", "name": "Default", "category": "built-in",
         "description": "Default Chatterbox voice"},
        {"voice_id": "clone", "name": "Clone (set voice_id to .wav path)",
         "category": "cloning", "description": "Voice cloning from reference audio"},
    ]


@app.post("/generate")
async def generate(req: GenerateRequest):
    from fastapi.responses import Response
    try:
        model = get_model()
        ref_audio = req.voice_id if os.path.isfile(req.voice_id) else None
        wav = model.generate(
            req.text,
            audio_prompt_path=ref_audio,
            exaggeration=req.exaggeration,
            cfg_weight=req.cfg_weight,
        )
        buf = io.BytesIO()
        torchaudio.save(buf, wav, model.sr, format="wav")
        return Response(content=buf.getvalue(), media_type="audio/wav")
    except Exception as e:
        raise HTTPException(500, detail=str(e))
