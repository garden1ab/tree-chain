"""Pydantic request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


# --- Script ---
class DialogueLineSchema(BaseModel):
    id: Optional[UUID] = None
    line_number: int
    character_name: str
    text: str
    raw_text: str
    directives: list[str] = []
    pause_after_ms: int = 0

    class Config:
        from_attributes = True


class ScriptUploadResponse(BaseModel):
    script_id: UUID
    filename: str
    total_lines: int
    characters: list[str]
    lines: list[DialogueLineSchema]


# --- Character Voice ---
class CharacterVoiceConfigSchema(BaseModel):
    character_name: str
    tts_provider: str = "elevenlabs"
    voice_id: str = ""
    model_id: str = "eleven_multilingual_v2"
    stability: float = Field(0.5, ge=0.0, le=1.0)
    similarity_boost: float = Field(0.75, ge=0.0, le=1.0)
    style: float = Field(0.0, ge=0.0, le=1.0)
    use_speaker_boost: bool = True
    # Chatterbox sliders (also map to other local models when applicable)
    exaggeration: float = Field(0.5, ge=0.25, le=2.0)
    cfg_weight: float = Field(0.5, ge=0.2, le=1.0)
    temperature: float = Field(0.8, ge=0.05, le=5.0)
    seed: int = 0
    language: str = "en"
    # Effects
    effects_preset: str = "none"
    effects_config: dict = {}
    volume_adjustment: float = Field(0.0, ge=-20.0, le=20.0)

    class Config:
        from_attributes = True


class CharacterVoiceConfigUpdate(BaseModel):
    configs: list[CharacterVoiceConfigSchema]


# --- Voice ---
class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    category: str = ""
    labels: dict = {}
    preview_url: Optional[str] = ""
    description: Optional[str] = ""


class VoiceListResponse(BaseModel):
    voices: list[VoiceInfo]
    models: list[dict] = []


# --- Generation ---
class GenerationRequest(BaseModel):
    project_id: UUID
    script_id: UUID
    export_mode: str = "individual"  # individual, combined, zip
    output_format: str = "wav"  # wav, mp3
    silence_between_ms: int = Field(500, ge=0, le=5000)
    normalize: bool = True
    line_ids: Optional[list[UUID]] = None  # None = all lines


class GenerationJobResponse(BaseModel):
    job_id: UUID
    status: str
    total_lines: int
    completed_lines: int
    failed_lines: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Project ---
class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str
    settings: dict = {}
    created_at: datetime

    class Config:
        from_attributes = True


# --- API Key ---
class ApiKeyCreate(BaseModel):
    provider: str = "elevenlabs"
    label: str = "Default"
    api_key: str


class ApiKeyResponse(BaseModel):
    id: UUID
    provider: str
    label: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyValidation(BaseModel):
    valid: bool
    message: str
    character_count: Optional[int] = None
    character_limit: Optional[int] = None


# --- Effects ---
class EffectPreviewRequest(BaseModel):
    audio_base64: str
    preset: str
    config: dict = {}


# --- Cost Estimation ---
class CostEstimate(BaseModel):
    total_characters: int
    estimated_credits: int
    estimated_duration_seconds: float
    line_count: int
    cached_lines: int


# --- Job Log ---
class JobLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    line_number: Optional[int] = None
    character: Optional[str] = None
