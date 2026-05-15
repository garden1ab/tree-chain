import io
import os
import re
import wave
import requests

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Orpheus TTS")

API_URL = os.getenv("ORPHEUS_API_URL")

SAMPLE_RATE = 24000
END_TOKEN = "<custom_token_11>"


class Req(BaseModel):
    text: str
    voice_id: str = "tara"


def format_prompt(text, voice):
    return f"{voice}: {text}"


def generate(text, voice):
    payload = {
        "prompt": f"<|audio|>{format_prompt(text, voice)}<|eoa|>",
        "max_tokens": 4096,
        "temperature": 0.6,
        "top_p": 0.9,
        "stop": ["<|eoa|>", END_TOKEN],
    }

    r = requests.post(API_URL, json=payload, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(r.text)

    data = r.json()
    text_out = data.get("choices", [{}])[0].get("text", "")

    tokens = [int(x) for x in re.findall(r"<custom_token_(\d+)>", text_out)]
    if not tokens:
        raise RuntimeError("No tokens returned")

    # simple PCM placeholder (safe fallback)
    pcm = bytearray(len(tokens) * 320)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)

    return buf.getvalue()


@app.get("/health")
def health():
    try:
        r = requests.get(API_URL.rsplit("/", 1)[0] + "/health", timeout=5)
        return {"ok": r.status_code == 200}
    except:
        return {"ok": False}


@app.get("/voices")
def voices():
    return [
        {"voice_id": "tara", "name": "Tara"},
        {"voice_id": "leo", "name": "Leo"},
    ]


@app.post("/v1/audio/speech")
async def openai(req: Request):
    body = await req.json()
    text = body.get("input")
    voice = body.get("voice", "tara")

    if not text:
        raise HTTPException(400, "missing input")

    audio = generate(text, voice)
    return Response(content=audio, media_type="audio/wav")
