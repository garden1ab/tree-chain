"""Kokoro TTS Service — Standalone container with Web UI and API."""

import io
import os
import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Kokoro TTS Service")

MODEL_DIR = os.environ.get("MODEL_DIR", "/app/models")
ONNX_PATH = os.path.join(MODEL_DIR, "kokoro-v0_19.onnx")
VOICES_PATH = os.path.join(MODEL_DIR, "voices.bin")

_model = None


def get_model():
    global _model
    if _model is None:
        from kokoro_onnx import Kokoro
        if not os.path.exists(ONNX_PATH):
            raise RuntimeError("Model not downloaded yet. Wait for startup to complete.")
        _model = Kokoro(ONNX_PATH, VOICES_PATH)
    return _model


VOICES = [
    ("af_alloy", "Alloy (US Female)"), ("af_aoede", "Aoede (US Female)"),
    ("af_bella", "Bella (US Female)"), ("af_jessica", "Jessica (US Female)"),
    ("af_kore", "Kore (US Female)"), ("af_nicole", "Nicole (US Female)"),
    ("af_nova", "Nova (US Female)"), ("af_river", "River (US Female)"),
    ("af_sarah", "Sarah (US Female)"), ("af_sky", "Sky (US Female)"),
    ("am_adam", "Adam (US Male)"), ("am_echo", "Echo (US Male)"),
    ("am_eric", "Eric (US Male)"), ("am_fenrir", "Fenrir (US Male)"),
    ("am_liam", "Liam (US Male)"), ("am_michael", "Michael (US Male)"),
    ("am_onyx", "Onyx (US Male)"), ("am_puck", "Puck (US Male)"),
    ("bf_alice", "Alice (British F)"), ("bf_emma", "Emma (British F)"),
    ("bf_isabella", "Isabella (British F)"), ("bf_lily", "Lily (British F)"),
    ("bm_daniel", "Daniel (British M)"), ("bm_fable", "Fable (British M)"),
    ("bm_george", "George (British M)"), ("bm_lewis", "Lewis (British M)"),
]


class GenerateRequest(BaseModel):
    text: str
    voice_id: str = "af_bella"
    speed: float = 1.0


@app.get("/health")
async def health():
    model_ready = os.path.exists(ONNX_PATH)
    return {"status": "ok" if model_ready else "downloading", "provider": "kokoro", "model_ready": model_ready}


@app.get("/voices")
async def list_voices():
    return [{"voice_id": vid, "name": name, "category": "built-in", "description": ""} for vid, name in VOICES]


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        import soundfile as sf
        model = get_model()
        voice = req.voice_id or "af_bella"
        samples, sr = model.create(req.text, voice=voice, speed=req.speed)
        buf = io.BytesIO()
        sf.write(buf, samples, sr, format="WAV")
        return Response(content=buf.getvalue(), media_type="audio/wav")
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# OpenAI-compatible endpoint
@app.post("/v1/audio/speech")
async def openai_speech(request: Request):
    try:
        import soundfile as sf
        body = await request.json()
        text = body.get("input", "")
        voice = body.get("voice", "af_bella")
        speed = body.get("speed", 1.0)
        model = get_model()
        samples, sr = model.create(text, voice=voice, speed=speed)
        buf = io.BytesIO()
        sf.write(buf, samples, sr, format="WAV")
        return Response(content=buf.getvalue(), media_type="audio/wav")
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ── Web UI ──
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    voice_options = "\n".join(f'<option value="{vid}">{name}</option>' for vid, name in VOICES)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kokoro TTS</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
  .container {{ max-width: 640px; width: 100%; padding: 2rem; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 1.5rem; color: #7c3aed; }}
  label {{ display: block; margin-bottom: 0.3rem; font-size: 0.85rem; color: #9ca3af; }}
  textarea, select, input {{ width: 100%; padding: 0.6rem; margin-bottom: 1rem; background: #1a1d27; border: 1px solid #2d3748; border-radius: 6px; color: #e0e0e0; font-size: 0.95rem; }}
  textarea {{ height: 120px; resize: vertical; }}
  .row {{ display: flex; gap: 1rem; }}
  .row > div {{ flex: 1; }}
  button {{ width: 100%; padding: 0.75rem; background: #7c3aed; color: white; border: none; border-radius: 6px; font-size: 1rem; cursor: pointer; }}
  button:hover {{ background: #6d28d9; }}
  button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
  #result {{ margin-top: 1rem; }}
  audio {{ width: 100%; margin-top: 0.5rem; }}
  .status {{ font-size: 0.85rem; color: #9ca3af; margin-top: 0.5rem; }}
</style>
</head>
<body>
<div class="container">
  <h1>🎙️ Kokoro TTS</h1>
  <label>Text</label>
  <textarea id="text" placeholder="Enter text to synthesize...">Hello! This is a test of the Kokoro text-to-speech system. It sounds pretty natural, don't you think?</textarea>
  <div class="row">
    <div><label>Voice</label><select id="voice">{voice_options}</select></div>
    <div><label>Speed</label><input id="speed" type="number" value="1.0" min="0.5" max="2.0" step="0.1"></div>
  </div>
  <button id="btn" onclick="generate()">Generate Speech</button>
  <div id="result"></div>
  <div class="status" id="status"></div>
</div>
<script>
async function generate() {{
  const btn = document.getElementById('btn');
  const status = document.getElementById('status');
  btn.disabled = true; status.textContent = 'Generating...';
  const t0 = Date.now();
  try {{
    const res = await fetch('/generate', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ text: document.getElementById('text').value, voice_id: document.getElementById('voice').value, speed: parseFloat(document.getElementById('speed').value) }})
    }});
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    document.getElementById('result').innerHTML = '<audio controls autoplay src="' + url + '"></audio>';
    status.textContent = 'Generated in ' + ((Date.now()-t0)/1000).toFixed(1) + 's';
  }} catch(e) {{ status.textContent = 'Error: ' + e.message; }}
  btn.disabled = false;
}}
</script>
</body>
</html>"""
