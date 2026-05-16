"""Chatterbox TTS Service — Full ResembleAI feature set + persistent voice library.

Endpoints:
  GET  /                          - Web UI
  GET  /health                    - Health check
  GET  /voices                    - List saved cloned voices + built-in
  POST /voices                    - Save a cloned voice (multipart: name, audio file)
  DELETE /voices/{voice_id}       - Delete a cloned voice
  GET  /voices/{voice_id}/sample  - Get the reference audio for a voice
  POST /generate                  - Generate speech (custom API)
  POST /v1/audio/speech           - Generate speech (OpenAI-compatible)
"""

import io
import os
import json
import time
import uuid
import random
import shutil
import struct
from pathlib import Path

import numpy as np
import torch
import torchaudio as ta
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse
from pydantic import BaseModel

# ── Setup ──
app = FastAPI(title="Chatterbox TTS Service")

VOICES_DIR = Path(os.environ.get("VOICES_DIR", "/app/voices"))
MODELS_DIR = Path(os.environ.get("MODELS_DIR", "/app/models"))
VOICES_META = VOICES_DIR / "voices.json"
VOICES_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🚀 Running on device: {DEVICE}")

_model = None


def get_model():
    """Lazy-load the Chatterbox model on first use."""
    global _model
    if _model is None:
        print("Loading Chatterbox model...")
        from chatterbox.tts import ChatterboxTTS
        _model = ChatterboxTTS.from_pretrained(DEVICE)
        if hasattr(_model, 'to'):
            try:
                _model.to(DEVICE)
            except Exception:
                pass
        print(f"Model loaded on {DEVICE}")
    return _model


def set_seed(seed: int):
    """Set seed across torch, numpy, and random."""
    torch.manual_seed(seed)
    if DEVICE == "cuda":
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    random.seed(seed)
    np.random.seed(seed)


# ── Voice library management ──
def load_voices_meta() -> dict:
    if VOICES_META.exists():
        try:
            return json.loads(VOICES_META.read_text())
        except Exception:
            return {}
    return {}


def save_voices_meta(meta: dict):
    VOICES_META.write_text(json.dumps(meta, indent=2))


# Built-in voices (no reference audio, uses default speaker)
BUILT_IN_VOICES = [
    {"voice_id": "default", "name": "Default Speaker", "category": "built-in", "description": "Chatterbox default voice"},
]


# ── API Models ──
class GenerateRequest(BaseModel):
    text: str
    voice_id: str = "default"
    exaggeration: float = 0.5
    cfg_weight: float = 0.5
    temperature: float = 0.8
    seed: int = 0


# ── Core generation ──
def synthesize(text: str, voice_id: str = "default",
               exaggeration: float = 0.5, cfg_weight: float = 0.5,
               temperature: float = 0.8, seed: int = 0) -> bytes:
    """Generate WAV bytes from text."""
    model = get_model()

    if seed and seed != 0:
        set_seed(int(seed))

    kwargs = {
        "exaggeration": float(exaggeration),
        "cfg_weight": float(cfg_weight),
        "temperature": float(temperature),
    }

    # Resolve voice: if it's a saved cloned voice, use its reference audio
    meta = load_voices_meta()
    if voice_id in meta:
        ref_path = VOICES_DIR / meta[voice_id]["filename"]
        if ref_path.exists():
            kwargs["audio_prompt_path"] = str(ref_path)
    # else: built-in / default — no audio_prompt_path

    # Truncate to 300 chars per official model behavior
    wav = model.generate(text[:300], **kwargs)

    # Convert tensor to WAV bytes
    buf = io.BytesIO()
    ta.save(buf, wav.cpu() if hasattr(wav, "cpu") else wav, model.sr, format="wav")
    return buf.getvalue()


# ── Endpoints ──
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "provider": "chatterbox",
        "device": DEVICE,
        "model_loaded": _model is not None,
    }


@app.get("/voices")
async def list_voices():
    meta = load_voices_meta()
    voices = list(BUILT_IN_VOICES)
    for vid, v in meta.items():
        voices.append({
            "voice_id": vid,
            "name": v.get("name", vid),
            "category": "cloned",
            "description": v.get("description", ""),
        })
    return voices


@app.post("/voices")
async def add_voice(
    name: str = Form(...),
    description: str = Form(""),
    audio: UploadFile = File(...),
):
    """Save a reference audio sample as a named cloned voice."""
    # Generate a slug-style voice_id from the name
    voice_id = name.lower().strip()
    voice_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in voice_id)
    if not voice_id:
        voice_id = f"voice_{uuid.uuid4().hex[:8]}"

    # Determine file extension from upload
    orig_ext = Path(audio.filename or "ref.wav").suffix.lower() or ".wav"
    if orig_ext not in {".wav", ".mp3", ".flac", ".ogg", ".m4a"}:
        orig_ext = ".wav"
    filename = f"{voice_id}{orig_ext}"

    # Save the audio file
    target = VOICES_DIR / filename
    with target.open("wb") as f:
        shutil.copyfileobj(audio.file, f)

    # Update metadata
    meta = load_voices_meta()
    meta[voice_id] = {
        "name": name,
        "filename": filename,
        "description": description,
        "created_at": time.time(),
    }
    save_voices_meta(meta)

    return {"voice_id": voice_id, "name": name, "filename": filename}


@app.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    meta = load_voices_meta()
    if voice_id not in meta:
        raise HTTPException(404, detail=f"Voice '{voice_id}' not found")
    # Delete file
    f = VOICES_DIR / meta[voice_id]["filename"]
    if f.exists():
        f.unlink()
    # Remove metadata
    del meta[voice_id]
    save_voices_meta(meta)
    return {"deleted": voice_id}


@app.get("/voices/{voice_id}/sample")
async def get_voice_sample(voice_id: str):
    """Return the reference audio for a saved cloned voice."""
    meta = load_voices_meta()
    if voice_id not in meta:
        raise HTTPException(404)
    f = VOICES_DIR / meta[voice_id]["filename"]
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(str(f))


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        audio = synthesize(
            req.text, req.voice_id,
            req.exaggeration, req.cfg_weight, req.temperature, req.seed,
        )
        return Response(content=audio, media_type="audio/wav")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))


@app.post("/v1/audio/speech")
async def openai_speech(request: Request):
    """OpenAI-compatible endpoint."""
    body = await request.json()
    text = body.get("input", "")
    voice = body.get("voice", "default")
    try:
        audio = synthesize(
            text, voice,
            float(body.get("exaggeration", 0.5)),
            float(body.get("cfg_weight", 0.5)),
            float(body.get("temperature", 0.8)),
            int(body.get("seed", 0)),
        )
        return Response(content=audio, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ── Web UI ──
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chatterbox TTS — Voice Cloning</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; padding: 1rem; }
  .container { max-width: 900px; margin: 0 auto; }
  h1 { font-size: 1.6rem; margin-bottom: 0.4rem; color: #ec4899; }
  .subtitle { font-size: 0.85rem; color: #9ca3af; margin-bottom: 1.5rem; }
  .tabs { display: flex; gap: 0; border-bottom: 1px solid #2d3748; margin-bottom: 1.5rem; }
  .tab { padding: 0.6rem 1.2rem; cursor: pointer; color: #9ca3af; border-bottom: 2px solid transparent; }
  .tab.active { color: #ec4899; border-color: #ec4899; }
  .panel { display: none; }
  .panel.active { display: block; }
  label { display: block; margin-bottom: 0.3rem; font-size: 0.85rem; color: #9ca3af; }
  textarea, select, input[type=text], input[type=number], input[type=file] { width: 100%; padding: 0.6rem; margin-bottom: 1rem; background: #1a1d27; border: 1px solid #2d3748; border-radius: 6px; color: #e0e0e0; font-size: 0.95rem; }
  textarea { height: 110px; resize: vertical; }
  input[type=range] { width: 100%; margin-bottom: 0.3rem; }
  .row { display: flex; gap: 1rem; flex-wrap: wrap; }
  .row > div { flex: 1; min-width: 150px; }
  .slider-row { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1rem; }
  .slider-row label { flex: 0 0 140px; margin: 0; }
  .slider-row input[type=range] { flex: 1; margin: 0; }
  .slider-row .val { flex: 0 0 50px; text-align: right; font-family: monospace; color: #ec4899; }
  button { padding: 0.7rem 1.2rem; background: #ec4899; color: white; border: none; border-radius: 6px; font-size: 0.95rem; cursor: pointer; font-weight: 500; }
  button:hover { background: #db2777; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  button.secondary { background: #374151; }
  button.secondary:hover { background: #4b5563; }
  button.danger { background: #dc2626; }
  button.danger:hover { background: #b91c1c; }
  .full-btn { width: 100%; padding: 0.85rem; font-size: 1rem; }
  #result { margin-top: 1rem; }
  audio { width: 100%; margin-top: 0.5rem; }
  .status { font-size: 0.85rem; color: #9ca3af; margin-top: 0.5rem; }
  .accordion { margin-bottom: 1rem; background: #1a1d27; border: 1px solid #2d3748; border-radius: 6px; padding: 0.6rem; }
  .accordion-header { cursor: pointer; font-size: 0.9rem; color: #9ca3af; user-select: none; }
  .accordion-content { display: none; margin-top: 0.8rem; }
  .accordion.open .accordion-content { display: block; }
  .voice-list { display: grid; gap: 0.6rem; margin-top: 1rem; }
  .voice-card { padding: 0.8rem; background: #1a1d27; border: 1px solid #2d3748; border-radius: 6px; display: flex; align-items: center; gap: 0.8rem; }
  .voice-card .info { flex: 1; }
  .voice-card .name { font-weight: 500; color: #e0e0e0; }
  .voice-card .desc { font-size: 0.8rem; color: #6b7280; }
  .voice-card .actions { display: flex; gap: 0.4rem; }
  .voice-card audio { width: 200px; margin: 0; }
  .badge { font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; background: #1e3a5f; color: #93c5fd; }
  .badge.cloned { background: #5b21b6; color: #ddd6fe; }
</style>
</head>
<body>
<div class="container">
  <h1>🎙️ Chatterbox TTS</h1>
  <p class="subtitle">Open-source ElevenLabs alternative with zero-shot voice cloning</p>

  <div class="tabs">
    <div class="tab active" onclick="switchTab('generate')">Generate</div>
    <div class="tab" onclick="switchTab('voices')">Voice Library</div>
  </div>

  <!-- GENERATE PANEL -->
  <div id="panel-generate" class="panel active">
    <label>Text (max 300 chars)</label>
    <textarea id="text" maxlength="300">Welcome to Chatterbox TTS. This is the first open-source text-to-speech model that beats ElevenLabs in blind listening tests.</textarea>

    <label>Voice</label>
    <select id="voice"><option>Loading...</option></select>

    <div class="slider-row">
      <label>Exaggeration</label>
      <input type="range" id="exag" min="0.25" max="2" step="0.05" value="0.5" oninput="document.getElementById('exag-val').textContent=this.value">
      <span class="val" id="exag-val">0.5</span>
    </div>
    <div class="slider-row">
      <label>CFG / Pace</label>
      <input type="range" id="cfg" min="0.2" max="1" step="0.05" value="0.5" oninput="document.getElementById('cfg-val').textContent=this.value">
      <span class="val" id="cfg-val">0.5</span>
    </div>

    <div class="accordion" id="acc-adv">
      <div class="accordion-header" onclick="document.getElementById('acc-adv').classList.toggle('open')">▸ More options</div>
      <div class="accordion-content">
        <div class="slider-row">
          <label>Temperature</label>
          <input type="range" id="temp" min="0.05" max="5" step="0.05" value="0.8" oninput="document.getElementById('temp-val').textContent=this.value">
          <span class="val" id="temp-val">0.8</span>
        </div>
        <label>Random seed (0 = random)</label>
        <input type="number" id="seed" value="0">
      </div>
    </div>

    <button class="full-btn" id="btn-gen" onclick="generate()">Generate Speech</button>
    <div id="result"></div>
    <div class="status" id="status"></div>
  </div>

  <!-- VOICES PANEL -->
  <div id="panel-voices" class="panel">
    <h2 style="font-size: 1.1rem; margin-bottom: 1rem; color: #ec4899;">Clone a New Voice</h2>
    <p style="font-size: 0.85rem; color: #9ca3af; margin-bottom: 1rem;">Upload a clean audio sample (5-30 seconds, single speaker, no background noise) to create a cloned voice you can reuse.</p>

    <label>Voice name (e.g. "Mary - British accent")</label>
    <input type="text" id="new-name" placeholder="My Character">

    <label>Description (optional)</label>
    <input type="text" id="new-desc" placeholder="e.g. Female, calm narrator voice">

    <label>Reference audio (.wav, .mp3, .flac, .ogg, .m4a)</label>
    <input type="file" id="new-audio" accept=".wav,.mp3,.flac,.ogg,.m4a">

    <button onclick="saveVoice()">Save Cloned Voice</button>
    <div class="status" id="save-status"></div>

    <h2 style="font-size: 1.1rem; margin: 2rem 0 0.5rem; color: #ec4899;">Saved Voices</h2>
    <div class="voice-list" id="voice-list">Loading...</div>
  </div>
</div>

<script>
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
  if (name === 'voices') loadVoiceList();
}

async function loadVoices() {
  try {
    const res = await fetch('/voices');
    const voices = await res.json();
    const sel = document.getElementById('voice');
    sel.innerHTML = '';
    voices.forEach(v => {
      const o = document.createElement('option');
      o.value = v.voice_id;
      o.textContent = `${v.name} ${v.category === 'cloned' ? '(cloned)' : ''}`;
      sel.appendChild(o);
    });
  } catch (e) { console.error(e); }
}

async function loadVoiceList() {
  const list = document.getElementById('voice-list');
  list.innerHTML = 'Loading...';
  try {
    const res = await fetch('/voices');
    const voices = await res.json();
    list.innerHTML = '';
    if (voices.length === 0) { list.innerHTML = '<p style="color:#6b7280">No voices yet.</p>'; return; }
    voices.forEach(v => {
      const card = document.createElement('div');
      card.className = 'voice-card';
      const sampleHtml = v.category === 'cloned'
        ? `<audio controls preload="none" src="/voices/${v.voice_id}/sample"></audio>`
        : '<span style="color:#6b7280;font-size:0.8rem">No reference</span>';
      const deleteHtml = v.category === 'cloned'
        ? `<button class="danger" onclick="deleteVoice('${v.voice_id}')">Delete</button>`
        : '';
      card.innerHTML = `
        <div class="info">
          <div class="name">${v.name} <span class="badge ${v.category}">${v.category}</span></div>
          <div class="desc">${v.description || v.voice_id}</div>
        </div>
        ${sampleHtml}
        <div class="actions">${deleteHtml}</div>
      `;
      list.appendChild(card);
    });
  } catch (e) { list.innerHTML = 'Error: ' + e.message; }
}

async function saveVoice() {
  const name = document.getElementById('new-name').value.trim();
  const desc = document.getElementById('new-desc').value.trim();
  const fileInput = document.getElementById('new-audio');
  const status = document.getElementById('save-status');
  if (!name) { status.textContent = 'Please enter a name'; return; }
  if (!fileInput.files[0]) { status.textContent = 'Please upload an audio file'; return; }
  const fd = new FormData();
  fd.append('name', name);
  fd.append('description', desc);
  fd.append('audio', fileInput.files[0]);
  status.textContent = 'Saving...';
  try {
    const res = await fetch('/voices', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    status.textContent = 'Saved!';
    document.getElementById('new-name').value = '';
    document.getElementById('new-desc').value = '';
    fileInput.value = '';
    await loadVoiceList();
    await loadVoices();
  } catch (e) { status.textContent = 'Error: ' + e.message; }
}

async function deleteVoice(id) {
  if (!confirm('Delete voice "' + id + '"?')) return;
  try {
    await fetch('/voices/' + id, { method: 'DELETE' });
    await loadVoiceList();
    await loadVoices();
  } catch (e) { alert(e.message); }
}

async function generate() {
  const btn = document.getElementById('btn-gen');
  const status = document.getElementById('status');
  btn.disabled = true; status.textContent = 'Generating (may take 10-30s on CPU)...';
  const t0 = Date.now();
  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: document.getElementById('text').value,
        voice_id: document.getElementById('voice').value,
        exaggeration: parseFloat(document.getElementById('exag').value),
        cfg_weight: parseFloat(document.getElementById('cfg').value),
        temperature: parseFloat(document.getElementById('temp').value),
        seed: parseInt(document.getElementById('seed').value) || 0,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    document.getElementById('result').innerHTML = '<audio controls autoplay src="' + url + '"></audio>';
    status.textContent = 'Generated in ' + ((Date.now()-t0)/1000).toFixed(1) + 's';
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
  }
  btn.disabled = false;
}

loadVoices();
</script>
</body>
</html>"""
