"""TTS provider abstraction — swap between ElevenLabs, Kokoro, Chatterbox, XTTS, Orpheus, etc."""

from __future__ import annotations
import hashlib
import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


# ── Data types ──────────────────────────────────────────

@dataclass
class TTSVoice:
    """A voice available from a provider."""
    voice_id: str
    name: str
    category: str = ""
    labels: dict = field(default_factory=dict)
    preview_url: str = ""
    description: str = ""


@dataclass
class TTSRequest:
    """Parameters for a TTS generation request."""
    text: str
    voice_id: str
    model_id: str = ""
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True


# ── Base class ──────────────────────────────────────────

class BaseTTSProvider(ABC):
    """Interface that all TTS providers implement."""

    name: str = "base"
    display_name: str = "Base Provider"
    requires_api_key: bool = False
    supports_voice_cloning: bool = False

    @abstractmethod
    async def generate_speech(self, request: TTSRequest) -> bytes:
        """Generate speech audio. Returns raw audio bytes (mp3 or wav)."""
        ...

    @abstractmethod
    def audio_format(self) -> str:
        """Return the format of bytes returned by generate_speech ('mp3' or 'wav')."""
        ...

    @abstractmethod
    async def list_voices(self) -> list[TTSVoice]:
        """Return voices available from this provider."""
        ...

    async def validate(self) -> tuple[bool, str]:
        """Check that the provider is ready (model loaded, API key valid, etc.)."""
        return True, "OK"

    @staticmethod
    def compute_cache_key(provider: str, text: str, voice_id: str, model_id: str,
                          stability: float, similarity: float, style: float) -> str:
        raw = f"{provider}|{text}|{voice_id}|{model_id}|{stability:.3f}|{similarity:.3f}|{style:.3f}"
        return hashlib.sha256(raw.encode()).hexdigest()


# ── ElevenLabs provider ────────────────────────────────

class ElevenLabsProvider(BaseTTSProvider):
    name = "elevenlabs"
    display_name = "ElevenLabs"
    requires_api_key = True
    supports_voice_cloning = True

    def __init__(self, api_key: str = "", base_url: str = "https://api.elevenlabs.io/v1",
                 max_concurrent: int = 5):
        self.api_key = api_key
        self.base_url = base_url
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def _headers(self, accept: str = "application/json") -> dict:
        return {"xi-api-key": self.api_key, "Accept": accept}

    def audio_format(self) -> str:
        return "mp3"

    async def generate_speech(self, request: TTSRequest) -> bytes:
        import httpx
        async with self._semaphore:
            url = f"{self.base_url}/text-to-speech/{request.voice_id}"
            payload = {
                "text": request.text,
                "model_id": request.model_id or "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": request.stability,
                    "similarity_boost": request.similarity_boost,
                    "style": request.style,
                    "use_speaker_boost": request.use_speaker_boost,
                },
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=self._headers(accept="audio/mpeg"))
                if response.status_code == 429:
                    raise RuntimeError("ElevenLabs rate limited")
                if response.status_code != 200:
                    raise RuntimeError(f"ElevenLabs API error {response.status_code}: {response.text[:200]}")
                return response.content

    async def list_voices(self) -> list[TTSVoice]:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/voices", headers=self._headers())
            if response.status_code != 200:
                raise RuntimeError(f"Failed to fetch voices: {response.status_code}")
            data = response.json()
            return [
                TTSVoice(
                    voice_id=v.get("voice_id", ""),
                    name=v.get("name") or "Unknown",
                    category=v.get("category") or "",
                    labels=v.get("labels") or {},
                    preview_url=v.get("preview_url") or "",
                    description=v.get("description") or "",
                )
                for v in data.get("voices", [])
            ]

    async def validate(self) -> tuple[bool, str]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.base_url}/user/subscription", headers=self._headers()
                )
                if response.status_code == 200:
                    info = response.json()
                    return True, f"Valid — {info.get('character_count', '?')}/{info.get('character_limit', '?')} chars used"
                return False, f"Invalid key (HTTP {response.status_code})"
        except Exception as e:
            return False, str(e)


# ── Local model providers ──────────────────────────────

class KokoroProvider(BaseTTSProvider):
    """Kokoro — 82M param, fast, runs on CPU. pip install kokoro-onnx"""
    name = "kokoro"
    display_name = "Kokoro (Local)"
    requires_api_key = False

    def __init__(self):
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from kokoro_onnx import Kokoro
                self._model = Kokoro("kokoro-v0_19.onnx", "voices.bin")
            except ImportError:
                raise RuntimeError(
                    "Kokoro not installed. Run: pip install kokoro-onnx && "
                    "python -c \"from kokoro_onnx import Kokoro; Kokoro('kokoro-v0_19.onnx','voices.bin')\""
                )

    def audio_format(self) -> str:
        return "wav"

    async def generate_speech(self, request: TTSRequest) -> bytes:
        import io, soundfile as sf
        self._load()
        voice = request.voice_id or "af_bella"
        samples, sr = self._model.create(request.text, voice=voice, speed=1.0)
        buf = io.BytesIO()
        sf.write(buf, samples, sr, format="WAV")
        return buf.getvalue()

    async def list_voices(self) -> list[TTSVoice]:
        # Kokoro built-in voices
        voices = [
            ("af_bella", "Bella (Female)"), ("af_sarah", "Sarah (Female)"),
            ("af_nicole", "Nicole (Female)"), ("af_sky", "Sky (Female)"),
            ("am_adam", "Adam (Male)"), ("am_michael", "Michael (Male)"),
            ("bf_emma", "Emma (British F)"), ("bm_george", "George (British M)"),
        ]
        return [TTSVoice(voice_id=vid, name=name, category="built-in") for vid, name in voices]

    async def validate(self) -> tuple[bool, str]:
        try:
            self._load()
            return True, "Kokoro model loaded"
        except Exception as e:
            return False, str(e)


class ChatterboxProvider(BaseTTSProvider):
    """Chatterbox by Resemble AI — 350M param, expressive. pip install chatterbox-tts"""
    name = "chatterbox"
    display_name = "Chatterbox (Local)"
    requires_api_key = False
    supports_voice_cloning = True

    def __init__(self):
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from chatterbox.tts import ChatterboxTTS
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                self._model = ChatterboxTTS.from_pretrained(device=device)
            except ImportError:
                raise RuntimeError("Chatterbox not installed. Run: pip install chatterbox-tts")

    def audio_format(self) -> str:
        return "wav"

    async def generate_speech(self, request: TTSRequest) -> bytes:
        import io, torchaudio
        self._load()
        # voice_id can be a path to a reference audio file for cloning
        ref_audio = request.voice_id if os.path.isfile(request.voice_id) else None
        wav = self._model.generate(request.text, audio_prompt_path=ref_audio)
        buf = io.BytesIO()
        torchaudio.save(buf, wav, self._model.sr, format="wav")
        return buf.getvalue()

    async def list_voices(self) -> list[TTSVoice]:
        return [
            TTSVoice(voice_id="default", name="Default", category="built-in",
                     description="Default Chatterbox voice"),
            TTSVoice(voice_id="clone", name="Clone (provide audio path)", category="cloning",
                     description="Set voice_id to a .wav file path to clone that voice"),
        ]

    async def validate(self) -> tuple[bool, str]:
        try:
            self._load()
            return True, "Chatterbox model loaded"
        except Exception as e:
            return False, str(e)


class XTTSProvider(BaseTTSProvider):
    """Coqui XTTS v2 — best voice cloning, multilingual. pip install TTS"""
    name = "xtts"
    display_name = "XTTS v2 / Coqui (Local)"
    requires_api_key = False
    supports_voice_cloning = True

    def __init__(self):
        self._tts = None

    def _load(self):
        if self._tts is None:
            try:
                from TTS.api import TTS
                self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
            except ImportError:
                raise RuntimeError("Coqui TTS not installed. Run: pip install TTS")
            except Exception:
                # Fall back to CPU
                from TTS.api import TTS
                self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)

    def audio_format(self) -> str:
        return "wav"

    async def generate_speech(self, request: TTSRequest) -> bytes:
        import tempfile
        self._load()
        ref_audio = request.voice_id if os.path.isfile(request.voice_id) else None
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            if ref_audio:
                self._tts.tts_to_file(
                    text=request.text,
                    speaker_wav=ref_audio,
                    language="en",
                    file_path=tmp_path,
                )
            else:
                self._tts.tts_to_file(text=request.text, file_path=tmp_path)

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def list_voices(self) -> list[TTSVoice]:
        return [
            TTSVoice(voice_id="default", name="Default XTTS", category="built-in"),
            TTSVoice(voice_id="clone", name="Clone (provide .wav path as voice_id)",
                     category="cloning",
                     description="Set voice_id to a .wav file path for 6-second voice cloning"),
        ]

    async def validate(self) -> tuple[bool, str]:
        try:
            self._load()
            return True, "XTTS v2 model loaded"
        except Exception as e:
            return False, str(e)


class OrpheusTTSProvider(BaseTTSProvider):
    """Orpheus TTS — 3B param, emotional control. pip install orpheus-tts"""
    name = "orpheus"
    display_name = "Orpheus TTS (Local)"
    requires_api_key = False

    def __init__(self):
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from orpheus_tts import OrpheusModel
                self._model = OrpheusModel(model_name="canopylabs/orpheus-tts-0.1-finetune-prod")
            except ImportError:
                raise RuntimeError("Orpheus TTS not installed. Run: pip install orpheus-tts")

    def audio_format(self) -> str:
        return "wav"

    async def generate_speech(self, request: TTSRequest) -> bytes:
        import io, struct, wave as wave_mod
        self._load()
        voice = request.voice_id or "tara"
        audio_chunks = self._model.generate_speech(
            prompt=request.text,
            voice=voice,
        )
        # Collect PCM samples from generator
        pcm_data = b""
        for chunk in audio_chunks:
            pcm_data += chunk

        # Wrap in WAV
        buf = io.BytesIO()
        with wave_mod.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm_data)
        return buf.getvalue()

    async def list_voices(self) -> list[TTSVoice]:
        voices = [
            ("tara", "Tara (Female)"), ("leah", "Leah (Female)"),
            ("jess", "Jess (Female)"), ("leo", "Leo (Male)"),
            ("dan", "Dan (Male)"), ("mia", "Mia (Female)"),
            ("zac", "Zac (Male)"), ("zoe", "Zoe (Female)"),
        ]
        return [TTSVoice(voice_id=vid, name=name, category="built-in") for vid, name in voices]

    async def validate(self) -> tuple[bool, str]:
        try:
            self._load()
            return True, "Orpheus model loaded"
        except Exception as e:
            return False, str(e)


class PiperProvider(BaseTTSProvider):
    """Piper — very fast, low resource, CPU-friendly. pip install piper-tts"""
    name = "piper"
    display_name = "Piper (Local, CPU)"
    requires_api_key = False

    def audio_format(self) -> str:
        return "wav"

    async def generate_speech(self, request: TTSRequest) -> bytes:
        import subprocess, tempfile
        voice = request.voice_id or "en_US-lessac-medium"
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            proc = subprocess.run(
                ["piper", "--model", voice, "--output_file", tmp_path],
                input=request.text.encode(),
                capture_output=True, timeout=30,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Piper failed: {proc.stderr.decode()[:200]}")
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def list_voices(self) -> list[TTSVoice]:
        voices = [
            ("en_US-lessac-medium", "Lessac (US Medium)"),
            ("en_US-lessac-high", "Lessac (US High)"),
            ("en_US-amy-medium", "Amy (US Medium)"),
            ("en_US-ryan-medium", "Ryan (US Medium)"),
            ("en_GB-alan-medium", "Alan (GB Medium)"),
            ("en_GB-alba-medium", "Alba (GB Medium)"),
        ]
        return [TTSVoice(voice_id=vid, name=name, category="built-in") for vid, name in voices]

    async def validate(self) -> tuple[bool, str]:
        import shutil
        if shutil.which("piper"):
            return True, "Piper CLI found"
        return False, "Piper not installed. Run: pip install piper-tts"


# ── Provider registry ──────────────────────────────────

_PROVIDERS: dict[str, BaseTTSProvider] = {}


def register_provider(provider: BaseTTSProvider):
    _PROVIDERS[provider.name] = provider


def get_provider(name: str) -> BaseTTSProvider:
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown TTS provider '{name}'. Available: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[name]


def list_providers() -> list[dict]:
    return [
        {
            "name": p.name,
            "display_name": p.display_name,
            "requires_api_key": p.requires_api_key,
            "supports_voice_cloning": p.supports_voice_cloning,
        }
        for p in _PROVIDERS.values()
    ]


def init_providers(api_key: str = ""):
    """Register all providers. Called at startup."""
    from app.core.config import get_settings
    settings = get_settings()

    register_provider(ElevenLabsProvider(
        api_key=api_key or settings.elevenlabs_api_key,
        base_url=settings.elevenlabs_base_url,
        max_concurrent=settings.max_concurrent_generations,
    ))
    register_provider(KokoroProvider())
    register_provider(ChatterboxProvider())
    register_provider(XTTSProvider())
    register_provider(OrpheusTTSProvider())
    register_provider(PiperProvider())
