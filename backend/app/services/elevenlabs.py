"""ElevenLabs TTS API integration with rate limiting and retry."""

import hashlib
import asyncio
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import get_settings

logger = structlog.get_logger()


class ElevenLabsError(Exception):
    pass


class ElevenLabsRateLimited(ElevenLabsError):
    pass


class ElevenLabsService:
    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.elevenlabs_api_key
        self.base_url = settings.elevenlabs_base_url
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_generations)

    def _headers(self) -> dict:
        return {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(ElevenLabsRateLimited),
    )
    async def generate_speech(
        self,
        text: str,
        voice_id: str,
        model_id: str = "eleven_multilingual_v2",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True,
    ) -> bytes:
        """Generate speech audio from text. Returns raw audio bytes."""
        async with self._semaphore:
            url = f"{self.base_url}/text-to-speech/{voice_id}"
            payload = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost,
                    "style": style,
                    "use_speaker_boost": use_speaker_boost,
                },
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=self._headers())

                if response.status_code == 429:
                    logger.warning("elevenlabs_rate_limited", voice_id=voice_id)
                    raise ElevenLabsRateLimited("Rate limited by ElevenLabs")

                if response.status_code != 200:
                    error_detail = response.text
                    logger.error("elevenlabs_error", status=response.status_code, detail=error_detail)
                    raise ElevenLabsError(f"ElevenLabs API error {response.status_code}: {error_detail}")

                return response.content

    async def list_voices(self) -> list[dict]:
        """Fetch available voices from ElevenLabs."""
        url = f"{self.base_url}/voices"
        headers = {**self._headers(), "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise ElevenLabsError(f"Failed to fetch voices: {response.status_code}")
            data = response.json()
            return data.get("voices", [])

    async def list_models(self) -> list[dict]:
        """Fetch available models."""
        url = f"{self.base_url}/models"
        headers = {**self._headers(), "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise ElevenLabsError(f"Failed to fetch models: {response.status_code}")
            return response.json()

    async def get_subscription_info(self) -> dict:
        """Get subscription/usage info for key validation."""
        url = f"{self.base_url}/user/subscription"
        headers = {**self._headers(), "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise ElevenLabsError(f"Invalid API key or request failed: {response.status_code}")
            return response.json()

    @staticmethod
    def compute_cache_key(text: str, voice_id: str, model_id: str,
                          stability: float, similarity: float, style: float) -> str:
        """Deterministic cache key from generation parameters."""
        raw = f"{text}|{voice_id}|{model_id}|{stability:.3f}|{similarity:.3f}|{style:.3f}"
        return hashlib.sha256(raw.encode()).hexdigest()
