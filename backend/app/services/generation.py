"""Generation service orchestrating TTS, effects, and export."""

import asyncio
import os
import re
import uuid
import zipfile
from datetime import datetime

import structlog
from pydub import AudioSegment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.effects import apply_effects, normalize_loudness, concatenate_audio, get_audio_duration_ms
from app.core.config import get_settings
from app.models.database import (
    CachedAudio, CharacterVoiceConfig, DialogueLine, GenerationJob,
    LineResult, JobStatus, Script
)
from app.services.tts_providers import get_provider, BaseTTSProvider, TTSRequest, init_providers

logger = structlog.get_logger()


def sanitize_filename(name: str) -> str:
    return re.sub(r'[^\w\-]', '_', name).strip('_')


def build_file_stem(character_name: str, text: str, line_number: int) -> str:
    """Build a filename stem in the format: Name_first20charactersOfText

    The line number is appended as a short suffix to guarantee uniqueness
    when two lines start with the same 20 characters.
    """
    safe_char = sanitize_filename(character_name)
    # First 20 characters of the dialogue text, sanitized
    snippet = sanitize_filename(text[:20])
    if snippet:
        stem = f"{safe_char}_{snippet}"
    else:
        stem = safe_char
    # Append line number to avoid collisions between identical snippets
    return f"{stem}_{line_number:03d}"


class GenerationService:
    def __init__(self, db: AsyncSession, api_key: str | None = None):
        self.db = db
        self.settings = get_settings()
        self.api_key = api_key
        self.log_callbacks: list = []
        # Ensure providers are registered (worker process may not have run startup)
        try:
            get_provider("elevenlabs")
        except ValueError:
            init_providers(api_key=api_key or "")

    def _log(self, level: str, message: str, **kwargs):
        entry = {"timestamp": datetime.utcnow().isoformat(), "level": level, "message": message, **kwargs}
        logger.msg(message, level=level, **kwargs)
        for cb in self.log_callbacks:
            try:
                cb(entry)
            except Exception:
                pass

    async def estimate_cost(self, script_id: uuid.UUID, project_id: uuid.UUID) -> dict:
        """Estimate generation cost before running."""
        lines = (await self.db.execute(
            select(DialogueLine).where(DialogueLine.script_id == script_id)
        )).scalars().all()

        total_chars = sum(len(line.text) for line in lines)
        cached = 0

        configs = (await self.db.execute(
            select(CharacterVoiceConfig).where(CharacterVoiceConfig.project_id == project_id)
        )).scalars().all()
        config_map = {c.character_name: c for c in configs}

        for line in lines:
            cfg = config_map.get(line.character_name)
            if cfg:
                cache_key = BaseTTSProvider.compute_cache_key(
                    cfg.tts_provider or "elevenlabs",
                    line.text, cfg.voice_id, cfg.model_id,
                    cfg.stability, cfg.similarity_boost, cfg.style
                )
                existing = (await self.db.execute(
                    select(CachedAudio).where(CachedAudio.cache_key == cache_key)
                )).scalar_one_or_none()
                if existing:
                    cached += 1

        return {
            "total_characters": total_chars,
            "estimated_credits": total_chars,  # ElevenLabs charges per character
            "estimated_duration_seconds": total_chars * 0.06,  # rough estimate
            "line_count": len(lines),
            "cached_lines": cached,
        }

    async def run_generation(
        self,
        job_id: uuid.UUID,
        script_id: uuid.UUID,
        project_id: uuid.UUID,
        export_mode: str = "individual",
        output_format: str = "wav",
        silence_ms: int = 500,
        normalize: bool = True,
        line_ids: list[uuid.UUID] | None = None,
    ):
        """Execute the full generation pipeline."""
        job = (await self.db.execute(
            select(GenerationJob).where(GenerationJob.id == job_id)
        )).scalar_one()
        job.status = JobStatus.RUNNING
        await self.db.commit()

        self._log("info", "Starting generation", job_id=str(job_id))

        try:
            # Fetch lines
            query = select(DialogueLine).where(DialogueLine.script_id == script_id)
            if line_ids:
                query = query.where(DialogueLine.id.in_(line_ids))
            query = query.order_by(DialogueLine.line_number)
            lines = (await self.db.execute(query)).scalars().all()

            # Fetch voice configs
            configs = (await self.db.execute(
                select(CharacterVoiceConfig).where(CharacterVoiceConfig.project_id == project_id)
            )).scalars().all()
            config_map = {c.character_name: c for c in configs}

            job.total_lines = len(lines)
            await self.db.commit()

            output_dir = os.path.join(self.settings.output_dir, str(job_id))
            os.makedirs(output_dir, exist_ok=True)

            generated_files: list[tuple[int, str]] = []

            # Generate each line
            for line in lines:
                cfg = config_map.get(line.character_name)
                if not cfg or not cfg.voice_id:
                    self._log("warning", f"No voice configured for {line.character_name}, skipping",
                             line_number=line.line_number, character=line.character_name)
                    job.failed_lines += 1
                    await self.db.commit()
                    continue

                line_result = LineResult(
                    job_id=job_id,
                    line_id=line.id,
                    status=JobStatus.RUNNING,
                    character_count=len(line.text),
                )
                self.db.add(line_result)
                await self.db.commit()

                try:
                    # Resolve TTS provider for this character
                    provider_name = cfg.tts_provider or "elevenlabs"
                    try:
                        provider = get_provider(provider_name)
                    except ValueError:
                        # Fall back to elevenlabs
                        provider = get_provider("elevenlabs")

                    # Check cache
                    cache_key = BaseTTSProvider.compute_cache_key(
                        provider_name, line.text, cfg.voice_id, cfg.model_id,
                        cfg.stability, cfg.similarity_boost, cfg.style
                    )
                    cached = (await self.db.execute(
                        select(CachedAudio).where(CachedAudio.cache_key == cache_key)
                    )).scalar_one_or_none()

                    file_stem = build_file_stem(line.character_name, line.text, line.line_number)
                    raw_path = os.path.join(output_dir, f"{file_stem}_raw.wav")
                    final_path = os.path.join(output_dir, f"{file_stem}.{output_format}")

                    if cached and os.path.exists(cached.audio_path):
                        self._log("info", f"Cache hit for line {line.line_number}",
                                 line_number=line.line_number, character=line.character_name)
                        raw_path = cached.audio_path
                    else:
                        # Generate via TTS provider
                        self._log("info", f"Generating line {line.line_number}: {line.character_name} ({provider_name})",
                                 line_number=line.line_number, character=line.character_name,
                                 provider=provider_name)

                        tts_request = TTSRequest(
                            text=line.text,
                            voice_id=cfg.voice_id,
                            model_id=cfg.model_id,
                            stability=cfg.stability,
                            similarity_boost=cfg.similarity_boost,
                            style=cfg.style,
                            use_speaker_boost=cfg.use_speaker_boost,
                            exaggeration=getattr(cfg, "exaggeration", 0.5) or 0.5,
                            cfg_weight=getattr(cfg, "cfg_weight", 0.5) or 0.5,
                            temperature=getattr(cfg, "temperature", 0.8) or 0.8,
                            seed=getattr(cfg, "seed", 0) or 0,
                            language=getattr(cfg, "language", "en") or "en",
                        )
                        audio_bytes = await provider.generate_speech(tts_request)
                        audio_fmt = provider.audio_format()

                        # Save raw audio and convert to WAV if needed
                        if audio_fmt == "wav":
                            with open(raw_path, 'wb') as f:
                                f.write(audio_bytes)
                        else:
                            tmp_path = raw_path.replace('.wav', f'.{audio_fmt}')
                            with open(tmp_path, 'wb') as f:
                                f.write(audio_bytes)
                            seg = AudioSegment.from_file(tmp_path, format=audio_fmt)
                            seg.export(raw_path, format="wav")
                            os.remove(tmp_path)

                        # Cache it
                        self.db.add(CachedAudio(
                            cache_key=cache_key,
                            audio_path=raw_path,
                            text_hash=cache_key[:64],
                            voice_id=cfg.voice_id,
                            settings_hash=cache_key,
                        ))
                        await self.db.commit()

                    # Apply effects
                    effects_preset = cfg.effects_preset or "none"
                    # Check for directive-based effects
                    for directive in (line.directives or []):
                        if directive in ("radio", "helmet", "robot", "telephone", "megaphone",
                                        "vhs", "corrupted_ai", "deep_space", "glitch", "alien"):
                            effects_preset = directive

                    processed_path = os.path.join(output_dir, f"{file_stem}_proc.wav")
                    await apply_effects(raw_path, processed_path, effects_preset, cfg.effects_config)

                    # Volume adjustment
                    if cfg.volume_adjustment != 0:
                        seg = AudioSegment.from_file(processed_path)
                        seg = seg + cfg.volume_adjustment
                        seg.export(processed_path, format="wav")

                    # Normalize
                    if normalize:
                        await normalize_loudness(processed_path, final_path)
                    else:
                        seg = AudioSegment.from_file(processed_path)
                        seg.export(final_path, format=output_format)

                    # Clean up intermediate
                    if os.path.exists(processed_path) and processed_path != final_path:
                        os.remove(processed_path)

                    duration = get_audio_duration_ms(final_path)
                    line_result.status = JobStatus.COMPLETED
                    line_result.audio_path = raw_path
                    line_result.processed_path = final_path
                    line_result.cache_key = cache_key
                    line_result.duration_ms = duration
                    job.completed_lines += 1

                    generated_files.append((line.line_number, final_path))

                    self._log("info", f"Completed line {line.line_number}", line_number=line.line_number,
                             character=line.character_name, duration_ms=duration)

                except Exception as e:
                    line_result.status = JobStatus.FAILED
                    line_result.error_message = str(e)
                    job.failed_lines += 1
                    self._log("error", f"Failed line {line.line_number}: {e}",
                             line_number=line.line_number, character=line.character_name)

                await self.db.commit()

            # Export
            generated_files.sort(key=lambda x: x[0])
            output_paths = [f for _, f in generated_files]

            if export_mode == "combined" and output_paths:
                combined_path = os.path.join(output_dir, f"combined.{output_format}")
                await concatenate_audio(output_paths, combined_path, silence_ms)
                job.output_path = combined_path
                self._log("info", "Combined audio created", path=combined_path)

            elif export_mode == "zip" and output_paths:
                zip_path = os.path.join(output_dir, "dialogue_export.zip")
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for path in output_paths:
                        zf.write(path, os.path.basename(path))
                job.output_path = zip_path
                self._log("info", "ZIP archive created", path=zip_path)

            else:
                job.output_path = output_dir

            job.status = JobStatus.COMPLETED
            self._log("info", "Generation job completed",
                      job_id=str(job_id), completed=job.completed_lines, failed=job.failed_lines)

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            self._log("error", f"Generation job failed: {e}", job_id=str(job_id))

        await self.db.commit()
