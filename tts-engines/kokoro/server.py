import io
import os
import soundfile as sf
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

app = FastAPI(title="Kokoro")

MODEL_DIR = os.getenv("MODEL_DIR", "/app/models")
ONNX = f"{MODEL_DIR}/kokoro-v0_19.onnx"
VOICES = f"{MODEL_DIR}/voices.bin"

_model = None


def load():
    global _model
    if _model is None:
        from kokoro_onnx import Kokoro
        _model = Kokoro(ONNX, VOICES)
    return _model


@app.get("/health")
def health():
    return {"ok": os.path.exists(ONNX)}


@app.get("/voices")
def voices():
    return [{"voice_id": "af_bella", "name": "Bella"}]


@app.post("/v1/audio/speech")
async def speech(req: Request):
    body = await req.json()
    text = body.get("input")
    voice = body.get("voice", "af_bella")
    speed = body.get("speed", 1.0)

    model = load()
    audio, sr = model.create(text, voice=voice, speed=speed)

    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")

    return Response(buf.getvalue(), media_type="audio/wav")
