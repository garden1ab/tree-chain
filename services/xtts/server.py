"""XTTS v2 / Coqui TTS service — runs as standalone container."""

import os
import tempfile
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="XTTS v2 TTS Service")

_tts = None


def get_tts():
    global _tts
    if _tts is None:
        from TTS.api import TTS
        try:
            _tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
            print("XTTS v2 loaded on GPU.")
        except Exception:
            _tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
            print("XTTS v2 loaded on CPU (no GPU available).")
    return _tts


class GenerateRequest(BaseModel):
    text: str
    voice_id: str = "default"
    language: str = "en"


@app.get("/health")
async def health():
    import torch
    return {"status": "ok", "provider": "xtts", "gpu": torch.cuda.is_available()}


@app.get("/voices")
async def list_voices():
    return [
        {"voice_id": "default", "name": "Default XTTS", "category": "built-in",
         "description": "Default XTTS v2 voice"},
        {"voice_id": "clone", "name": "Clone (set voice_id to .wav path)",
         "category": "cloning",
         "description": "Zero-shot voice cloning — provide a 6+ second .wav file path"},
    ]


@app.post("/generate")
async def generate(req: GenerateRequest):
    from fastapi.responses import Response
    try:
        tts = get_tts()
        ref_audio = req.voice_id if os.path.isfile(req.voice_id) else None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            if ref_audio:
                tts.tts_to_file(
                    text=req.text,
                    speaker_wav=ref_audio,
                    language=req.language,
                    file_path=tmp_path,
                )
            else:
                tts.tts_to_file(text=req.text, file_path=tmp_path)

            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(500, detail=str(e))
