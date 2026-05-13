"""Orpheus TTS service — runs as standalone container."""

import io
import wave
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Orpheus TTS Service")

_model = None


def get_model():
    global _model
    if _model is None:
        from orpheus_tts import OrpheusModel
        print("Loading Orpheus TTS...")
        _model = OrpheusModel(model_name="canopylabs/orpheus-tts-0.1-finetune-prod")
        print("Orpheus TTS ready.")
    return _model


class GenerateRequest(BaseModel):
    text: str
    voice_id: str = "tara"


@app.get("/health")
async def health():
    import torch
    return {"status": "ok", "provider": "orpheus", "gpu": torch.cuda.is_available()}


@app.get("/voices")
async def list_voices():
    voices = [
        ("tara", "Tara (Female)"), ("leah", "Leah (Female)"),
        ("jess", "Jess (Female)"), ("leo", "Leo (Male)"),
        ("dan", "Dan (Male)"), ("mia", "Mia (Female)"),
        ("zac", "Zac (Male)"), ("zoe", "Zoe (Female)"),
    ]
    return [
        {"voice_id": vid, "name": name, "category": "built-in", "description": ""}
        for vid, name in voices
    ]


@app.post("/generate")
async def generate(req: GenerateRequest):
    from fastapi.responses import Response
    try:
        model = get_model()
        voice = req.voice_id or "tara"
        audio_chunks = model.generate_speech(prompt=req.text, voice=voice)

        pcm_data = b""
        for chunk in audio_chunks:
            pcm_data += chunk

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm_data)

        return Response(content=buf.getvalue(), media_type="audio/wav")
    except Exception as e:
        raise HTTPException(500, detail=str(e))
