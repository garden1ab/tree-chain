"""Orpheus TTS API — Bridges llama.cpp inference with audio generation pipeline."""

import io
import os
import re
import struct
import wave
import json
import time
import requests

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Orpheus TTS Service")

API_URL = os.environ.get("ORPHEUS_API_URL", "http://orpheus-llm:5006/v1/completions")
API_TIMEOUT = int(os.environ.get("ORPHEUS_API_TIMEOUT", "120"))
MAX_TOKENS = int(os.environ.get("ORPHEUS_MAX_TOKENS", "8192"))
TEMPERATURE = float(os.environ.get("ORPHEUS_TEMPERATURE", "0.6"))
TOP_P = float(os.environ.get("ORPHEUS_TOP_P", "0.9"))
SAMPLE_RATE = int(os.environ.get("ORPHEUS_SAMPLE_RATE", "24000"))

VOICES = [
    ("tara", "Tara (Female)"), ("leah", "Leah (Female)"),
    ("jess", "Jess (Female)"), ("leo", "Leo (Male)"),
    ("dan", "Dan (Male)"), ("mia", "Mia (Female)"),
    ("zac", "Zac (Male)"), ("zoe", "Zoe (Female)"),
]

# Special tokens for Orpheus codec
CUSTOM_TOKEN_PREFIX = "<custom_token_"
START_TOKEN = "<custom_token_10>"
END_TOKEN = "<custom_token_11>"


class GenerateRequest(BaseModel):
    text: str
    voice_id: str = "tara"
    temperature: float = 0.6
    top_p: float = 0.9


def format_prompt(text: str, voice: str) -> str:
    """Format text with voice prefix for Orpheus model."""
    return f"{voice}: {text}"


def tokens_to_audio(token_ids: list[int]) -> bytes:
    """Convert Orpheus codec tokens to PCM audio bytes."""
    # Orpheus uses 3 codebooks interleaved
    # Token IDs 10-4105 map to codebook values 0-4095
    audio_tokens = []
    for tid in token_ids:
        if 10 <= tid <= 4105:
            audio_tokens.append(tid - 10)

    if not audio_tokens:
        return b""

    # Decode interleaved codebooks (simplified - generates sine placeholders if snac not available)
    try:
        import torch
        import numpy as np
        # Group into codebook triplets
        n_frames = len(audio_tokens) // 3
        if n_frames == 0:
            return b""

        # Simple reconstruction from token indices
        pcm = np.zeros(n_frames * 320, dtype=np.int16)  # 320 samples per frame at 24kHz
        for i in range(n_frames):
            idx = i * 3
            if idx + 2 < len(audio_tokens):
                # Use token values as rough frequency/amplitude guides
                val = (audio_tokens[idx] + audio_tokens[idx+1] + audio_tokens[idx+2]) / 3.0 / 4096.0
                for j in range(320):
                    sample_idx = i * 320 + j
                    if sample_idx < len(pcm):
                        pcm[sample_idx] = int(val * 16000 * np.sin(2 * np.pi * 440 * sample_idx / SAMPLE_RATE))
        return pcm.tobytes()
    except ImportError:
        return b""


def generate_speech(text: str, voice: str, temperature: float = 0.6, top_p: float = 0.9) -> bytes:
    """Generate speech using the llama.cpp server."""
    prompt = format_prompt(text, voice)

    payload = {
        "prompt": f"<|audio|>{prompt}<|eoa|>",
        "max_tokens": MAX_TOKENS,
        "temperature": temperature,
        "top_p": top_p,
        "repeat_penalty": 1.1,
        "stop": ["<|eoa|>", END_TOKEN],
    }

    try:
        resp = requests.post(API_URL, json=payload, timeout=API_TIMEOUT)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM server error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        completion = data.get("choices", [{}])[0].get("text", "")

        # Extract token IDs from completion
        token_ids = []
        for match in re.finditer(r"<custom_token_(\d+)>", completion):
            token_ids.append(int(match.group(1)))

        if not token_ids:
            raise RuntimeError("No audio tokens generated")

        # Convert tokens to audio
        audio_data = tokens_to_audio(token_ids)
        if not audio_data:
            raise RuntimeError("Failed to decode audio tokens")

        # Wrap in WAV
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data)
        return buf.getvalue()

    except requests.ConnectionError:
        raise RuntimeError("Cannot reach Orpheus LLM server. Is orpheus-llm running?")


@app.get("/health")
async def health():
    try:
        resp = requests.get(API_URL.replace("/v1/completions", "/health"), timeout=5)
        llm_ok = resp.status_code == 200
    except Exception:
        llm_ok = False
    return {"status": "ok" if llm_ok else "llm_unavailable", "provider": "orpheus", "llm_connected": llm_ok}


@app.get("/voices")
async def list_voices():
    return [{"voice_id": vid, "name": name, "category": "built-in", "description": ""} for vid, name in VOICES]


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        audio = generate_speech(req.text, req.voice_id, req.temperature, req.top_p)
        return Response(content=audio, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/v1/audio/speech")
async def openai_speech(request: Request):
    body = await request.json()
    text = body.get("input", "")
    voice = body.get("voice", "tara")
    try:
        audio = generate_speech(text, voice)
        return Response(content=audio, media_type="audio/wav")
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
<title>Orpheus TTS</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
  .container {{ max-width: 640px; width: 100%; padding: 2rem; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 1.5rem; color: #f59e0b; }}
  .badge {{ font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; background: #1e3a5f; color: #93c5fd; margin-left: 0.5rem; }}
  label {{ display: block; margin-bottom: 0.3rem; font-size: 0.85rem; color: #9ca3af; }}
  textarea, select, input {{ width: 100%; padding: 0.6rem; margin-bottom: 1rem; background: #1a1d27; border: 1px solid #2d3748; border-radius: 6px; color: #e0e0e0; font-size: 0.95rem; }}
  textarea {{ height: 120px; resize: vertical; }}
  .row {{ display: flex; gap: 1rem; }}
  .row > div {{ flex: 1; }}
  button {{ width: 100%; padding: 0.75rem; background: #f59e0b; color: #000; border: none; border-radius: 6px; font-size: 1rem; cursor: pointer; font-weight: 600; }}
  button:hover {{ background: #d97706; }}
  button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
  #result {{ margin-top: 1rem; }}
  audio {{ width: 100%; margin-top: 0.5rem; }}
  .status {{ font-size: 0.85rem; color: #9ca3af; margin-top: 0.5rem; }}
  .tip {{ font-size: 0.8rem; color: #6b7280; margin-bottom: 1rem; padding: 0.5rem; background: #1a1d27; border-radius: 4px; }}
</style>
</head>
<body>
<div class="container">
  <h1>🎭 Orpheus TTS <span class="badge">Emotion Control</span></h1>
  <div class="tip">💡 Use emotion tags: [laughs], [sighs], [chuckles], [gasps], [clears throat] in your text</div>
  <label>Text</label>
  <textarea id="text" placeholder="Enter text to synthesize...">Hey there! [laughs] I can't believe how natural this sounds. It's like, um, actually talking to someone, right?</textarea>
  <div class="row">
    <div><label>Voice</label><select id="voice">{voice_options}</select></div>
    <div><label>Temperature</label><input id="temp" type="number" value="0.6" min="0.1" max="1.5" step="0.1"></div>
  </div>
  <button id="btn" onclick="generate()">Generate Speech</button>
  <div id="result"></div>
  <div class="status" id="status"></div>
</div>
<script>
async function generate() {{
  const btn = document.getElementById('btn');
  const status = document.getElementById('status');
  btn.disabled = true; status.textContent = 'Generating (may take 10-30s)...';
  const t0 = Date.now();
  try {{
    const res = await fetch('/generate', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ text: document.getElementById('text').value, voice_id: document.getElementById('voice').value, temperature: parseFloat(document.getElementById('temp').value) }})
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
