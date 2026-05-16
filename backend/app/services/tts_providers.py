"""TTS provider abstraction — ElevenLabs (cloud), Kokoro/Piper (in-process), Chatterbox/XTTS/Orpheus (sidecar containers)."""

from __future__ import annotations
import hashlib
import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx
import structlog

logger = structlog.get_logger()


# ── Data types ──────────────────────────────────────────

@dataclass
class TTSVoice:
    voice_id: str
    name: str
    category: str = ""
    labels: dict = field(default_factory=dict)
    preview_url: str = ""
    description: str = ""


@dataclass
class TTSRequest:
    text: str
    voice_id: str
    model_id: str = ""
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True


# ── Base class ──────────────────────────────────────────

class BaseTTSProvider(ABC):
    name: str = "base"
    display_name: str = "Base Provider"
    requires_api_key: bool = False
    supports_voice_cloning: bool = False

    @abstractmethod
    async def generate_speech(self, request: TTSRequest) -> bytes:
        ...

    @abstractmethod
    def audio_format(self) -> str:
        ...

    @abstractmethod
    async def list_voices(self) -> list[TTSVoice]:
        ...

    async def validate(self) -> tuple[bool, str]:
        return True, "OK"

    @staticmethod
    def compute_cache_key(provider: str, text: str, voice_id: str, model_id: str,
                          stability: float, similarity: float, style: float) -> str:
        raw = f"{provider}|{text}|{voice_id}|{model_id}|{stability:.3f}|{similarity:.3f}|{style:.3f}"
        return hashlib.sha256(raw.encode()).hexdigest()


# ── ElevenLabs (cloud API) ─────────────────────────────

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
                resp = await client.post(url, json=payload, headers=self._headers(accept="audio/mpeg"))
                if resp.status_code == 429:
                    raise RuntimeError("ElevenLabs rate limited")
                if resp.status_code != 200:
                    raise RuntimeError(f"ElevenLabs error {resp.status_code}: {resp.text[:200]}")
                return resp.content

    async def list_voices(self) -> list[TTSVoice]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}/voices", headers=self._headers())
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch voices: {resp.status_code}")
            return [
                TTSVoice(
                    voice_id=v.get("voice_id", ""),
                    name=v.get("name") or "Unknown",
                    category=v.get("category") or "",
                    labels=v.get("labels") or {},
                    preview_url=v.get("preview_url") or "",
                    description=v.get("description") or "",
                )
                for v in resp.json().get("voices", [])
            ]

    async def validate(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.base_url}/user/subscription", headers=self._headers())
                if resp.status_code == 200:
                    info = resp.json()
                    return True, f"Valid — {info.get('character_count', '?')}/{info.get('character_limit', '?')} chars"
                return False, f"Invalid key (HTTP {resp.status_code})"
        except Exception as e:
            return False, str(e)


# ── Kokoro (in-process, CPU) ───────────────────────────

class KokoroProvider(BaseTTSProvider):
    name = "kokoro"
    display_name = "Kokoro (Local)"
    requires_api_key = False

    MODEL_DIR = "/app/models/kokoro"

    def __init__(self):
        self._model = None

    def _load(self):
        if self._model is None:
            import time
            from kokoro_onnx import Kokoro
            onnx_path = os.path.join(self.MODEL_DIR, "kokoro-v0_19.onnx")
            voices_path = os.path.join(self.MODEL_DIR, "voices.bin")
            done_path = os.path.join(self.MODEL_DIR, ".done")

            # Wait up to 5 minutes for the background download to finish
            waited = 0
            while not os.path.exists(done_path) and waited < 300:
                logger.info("kokoro.waiting_for_download", waited=waited)
                time.sleep(5)
                waited += 5

            if not os.path.exists(onnx_path) or not os.path.exists(voices_path):
                raise RuntimeError(
                    f"Kokoro model files not found in {self.MODEL_DIR}. "
                    "The download may still be in progress — try again in a minute."
                )
            self._model = Kokoro(onnx_path, voices_path)

    def audio_format(self) -> str:
        return "wav"

    async def generate_speech(self, request: TTSRequest) -> bytes:
        import io
        import soundfile as sf
        self._load()
        voice = request.voice_id or "af_bella"
        samples, sr = self._model.create(request.text, voice=voice, speed=1.0)
        buf = io.BytesIO()
        sf.write(buf, samples, sr, format="WAV")
        return buf.getvalue()

    async def list_voices(self) -> list[TTSVoice]:
        return [
            TTSVoice(vid, name, "built-in") for vid, name in [
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
        ]

    async def validate(self) -> tuple[bool, str]:
        try:
            self._load()
            return True, "Kokoro model loaded"
        except Exception as e:
            return False, f"Not installed: {e}"


# ── Piper (in-process, CPU) ────────────────────────────

class PiperProvider(BaseTTSProvider):
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
                input=request.text.encode(), capture_output=True, timeout=30,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Piper failed: {proc.stderr.decode()[:200]}")
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def list_voices(self) -> list[TTSVoice]:
        return [
            TTSVoice(vid, name, "built-in") for vid, name in [
                ("en_US-lessac-medium", "Lessac (US Medium)"),
                ("en_US-lessac-high", "Lessac (US High)"),
                ("en_US-amy-medium", "Amy (US Medium)"),
                ("en_US-ryan-medium", "Ryan (US Medium)"),
                ("en_GB-alan-medium", "Alan (GB Medium)"),
                ("en_GB-alba-medium", "Alba (GB Medium)"),
            ]
        ]

    async def validate(self) -> tuple[bool, str]:
        import shutil
        return (True, "Piper CLI found") if shutil.which("piper") else (False, "piper not installed")


# ── Sidecar provider (calls a container over HTTP) ─────

class SidecarProvider(BaseTTSProvider):
    """Generic provider that delegates to a sidecar TTS container via HTTP.

    Supports two API styles:
    - 'openai': Chatterbox-style — POST /v1/audio/speech with {"input": text, "voice": id}
    - 'custom': Our Kokoro/Orpheus servers — POST /generate with {"text": text, "voice_id": id}
    """

    # Hardcoded voice lists for services that don't expose a /voices endpoint
    CHATTERBOX_VOICES = [
        ("alloy", "Alloy"), ("echo", "Echo"), ("fable", "Fable"),
        ("onyx", "Onyx"), ("nova", "Nova"), ("shimmer", "Shimmer"),
    ]

    def __init__(self, name: str, display_name: str, base_url: str,
                 supports_cloning: bool = False, api_style: str = "custom"):
        self.name = name
        self.display_name = display_name
        self.base_url = base_url.rstrip("/")
        self.supports_voice_cloning = supports_cloning
        self.api_style = api_style  # 'openai' or 'custom'

    def audio_format(self) -> str:
        return "wav"

    async def generate_speech(self, request: TTSRequest) -> bytes:
        if self.api_style == "openai":
            # Chatterbox-style OpenAI-compatible endpoint
            endpoint = f"{self.base_url}/v1/audio/speech"
            payload = {
                "input": request.text,
                "voice": request.voice_id or "alloy",
            }
        else:
            # Custom Kokoro/Orpheus endpoint
            endpoint = f"{self.base_url}/generate"
            payload = {"text": request.text, "voice_id": request.voice_id}

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(endpoint, json=payload)
            if resp.status_code != 200:
                detail = resp.text[:300]
                raise RuntimeError(f"{self.display_name} error {resp.status_code}: {detail}")
            return resp.content

    async def list_voices(self) -> list[TTSVoice]:
        # Chatterbox: try /v1/audio/voices, fall back to hardcoded OpenAI voices
        if self.api_style == "openai":
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{self.base_url}/v1/audio/voices")
                    if resp.status_code == 200:
                        data = resp.json()
                        # response could be {"voices": [...]} or just a list
                        voices = data.get("voices", data) if isinstance(data, dict) else data
                        result = []
                        for v in voices:
                            if isinstance(v, dict):
                                result.append(TTSVoice(
                                    voice_id=v.get("voice_id") or v.get("value") or v.get("name", ""),
                                    name=v.get("label") or v.get("name", "Unknown"),
                                    category="built-in",
                                    description="",
                                ))
                            elif isinstance(v, str):
                                result.append(TTSVoice(v, v.title(), "built-in"))
                        if result:
                            return result
            except Exception:
                pass
            # Hardcoded fallback for Chatterbox
            return [TTSVoice(vid, name, "built-in") for vid, name in self.CHATTERBOX_VOICES]

        # Custom servers (Kokoro/Orpheus): use /voices
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/voices")
                if resp.status_code == 200:
                    return [
                        TTSVoice(
                            voice_id=v.get("voice_id", ""),
                            name=v.get("name", "Unknown"),
                            category=v.get("category", ""),
                            description=v.get("description", ""),
                        )
                        for v in resp.json()
                    ]
        except Exception:
            pass
        return [TTSVoice("default", f"{self.display_name} Default", "built-in")]

    async def validate(self) -> tuple[bool, str]:
        # Chatterbox health endpoint differs from our custom servers
        health_url = f"{self.base_url}/health" if self.api_style == "custom" else f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(health_url)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        gpu = data.get("gpu", data.get("device", "cpu"))
                        return True, f"Ready ({gpu})"
                    except Exception:
                        return True, "Ready"
                return False, f"Service returned {resp.status_code}"
        except httpx.ConnectError:
            return False, f"Service not running at {self.base_url}"
        except Exception as e:
            return False, str(e)


# ── Registry ───────────────────────────────────────────

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

    # Cloud
    register_provider(ElevenLabsProvider(
        api_key=api_key or settings.elevenlabs_api_key,
        base_url=settings.elevenlabs_base_url,
        max_concurrent=settings.max_concurrent_generations,
    ))

    # All local models run as separate services, connected via HTTP
    # Start them with: cd tts-engines && docker compose up

    register_provider(SidecarProvider(
        name="chatterbox",
        display_name="Chatterbox (Best Quality)",
        base_url=os.environ.get("CHATTERBOX_URL", "http://host.docker.internal:4123"),
        supports_cloning=True,
        api_style="openai",
    ))
    register_provider(SidecarProvider(
        name="orpheus",
        display_name="Orpheus (Emotion Control)",
        base_url=os.environ.get("ORPHEUS_URL", "http://host.docker.internal:8899"),
        supports_cloning=False,
        api_style="custom",
    ))
    register_provider(SidecarProvider(
        name="kokoro",
        display_name="Kokoro (Fast, CPU)",
        base_url=os.environ.get("KOKORO_URL", "http://host.docker.internal:8880"),
        supports_cloning=False,
        api_style="custom",
    ))
    register_provider(SidecarProvider(
        name="xtts",
        display_name="XTTS v2 (Multilingual)",
        base_url=os.environ.get("XTTS_URL", "http://host.docker.internal:5500"),
        supports_cloning=True,
        api_style="custom",
    ))
