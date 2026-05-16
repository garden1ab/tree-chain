"""SQLAlchemy database models."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime,
    JSON, ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("GenerationJob", back_populates="project", cascade="all, delete-orphan")


class Script(Base):
    __tablename__ = "scripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    raw_content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="scripts")
    lines = relationship("DialogueLine", back_populates="script", cascade="all, delete-orphan")


class DialogueLine(Base):
    __tablename__ = "dialogue_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False)
    line_number = Column(Integer, nullable=False)
    character_name = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=False)  # with markup tags
    directives = Column(JSON, default=list)  # parsed [tags]
    pause_after_ms = Column(Integer, default=0)

    script = relationship("Script", back_populates="lines")


class CharacterVoiceConfig(Base):
    __tablename__ = "character_voice_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    character_name = Column(String(255), nullable=False)
    tts_provider = Column(String(50), default="elevenlabs")
    voice_id = Column(String(255), default="")
    model_id = Column(String(255), default="eleven_multilingual_v2")
    # ElevenLabs sliders
    stability = Column(Float, default=0.5)
    similarity_boost = Column(Float, default=0.75)
    style = Column(Float, default=0.0)
    use_speaker_boost = Column(Boolean, default=True)
    # Chatterbox/local model sliders
    exaggeration = Column(Float, default=0.5)
    cfg_weight = Column(Float, default=0.5)
    temperature = Column(Float, default=0.8)
    seed = Column(Integer, default=0)
    language = Column(String(10), default="en")
    # Effects
    effects_preset = Column(String(100), default="none")
    effects_config = Column(JSON, default=dict)
    volume_adjustment = Column(Float, default=0.0)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    total_lines = Column(Integer, default=0)
    completed_lines = Column(Integer, default=0)
    failed_lines = Column(Integer, default=0)
    export_mode = Column(String(50), default="individual")  # individual, combined, zip
    output_format = Column(String(10), default="wav")
    output_path = Column(Text, default="")
    error_message = Column(Text, default="")
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="jobs")
    line_results = relationship("LineResult", back_populates="job", cascade="all, delete-orphan")


class LineResult(Base):
    __tablename__ = "line_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("generation_jobs.id"), nullable=False)
    line_id = Column(UUID(as_uuid=True), ForeignKey("dialogue_lines.id"), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    audio_path = Column(Text, default="")
    processed_path = Column(Text, default="")
    cache_key = Column(String(255), default="")
    error_message = Column(Text, default="")
    duration_ms = Column(Integer, default=0)
    character_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("GenerationJob", back_populates="line_results")


class CachedAudio(Base):
    __tablename__ = "cached_audio"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    audio_path = Column(Text, nullable=False)
    text_hash = Column(String(64), nullable=False)
    voice_id = Column(String(255), nullable=False)
    settings_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class StoredApiKey(Base):
    __tablename__ = "stored_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), default="elevenlabs")
    label = Column(String(255), default="Default")
    encrypted_key = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
