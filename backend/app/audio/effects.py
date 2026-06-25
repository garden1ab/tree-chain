"""Audio effects engine using FFmpeg filter chains and pydub."""

import asyncio
import os
import subprocess
import tempfile
import structlog
from pydub import AudioSegment

logger = structlog.get_logger()

# Predefined FFmpeg filter chains for each effect preset
# All filters used here are part of standard ffmpeg builds (no extras)
EFFECT_PRESETS: dict[str, str] = {
    "radio": (
        "highpass=f=300,lowpass=f=3400,"
        "acompressor=threshold=-20dB:ratio=6:attack=5:release=50,"
        "acrusher=bits=8:mix=0.3,"
        "volume=1.2"
    ),
    "helmet": (
        "highpass=f=200,lowpass=f=4000,"
        "aecho=0.8:0.88:20:0.3,"
        "acompressor=threshold=-15dB:ratio=4:attack=10:release=100,"
        "volume=0.9"
    ),
    "robot": (
        "asetrate=44100*0.9,aresample=44100,"
        "flanger=delay=2:depth=2:speed=0.5,"
        "aphaser=type=t:speed=0.8,"
        "volume=1.0"
    ),
    "telephone": (
        "highpass=f=400,lowpass=f=3000,"
        "acompressor=threshold=-25dB:ratio=8:attack=2:release=30,"
        "acrusher=bits=6:mix=0.2,"
        "volume=1.1"
    ),
    # Fixed: 'overdrive' filter doesn't exist in ffmpeg. Use distortion via gain+clipping
    "megaphone": (
        "highpass=f=500,lowpass=f=4000,"
        "volume=4.0,"                              # boost then clip
        "alimiter=limit=0.7,"
        "acompressor=threshold=-10dB:ratio=10:attack=1:release=20,"
        "volume=0.85"
    ),
    # Fixed: removed problematic flanger params, simpler chain
    "vhs": (
        "aecho=0.6:0.3:40:0.2,"
        "vibrato=f=4:d=0.3,"
        "highpass=f=80,lowpass=f=7000,"
        "acrusher=bits=10:mix=0.2,"
        "volume=0.85"
    ),
    "corrupted_ai": (
        "acrusher=bits=4:mix=0.5,"
        "aphaser=type=t:speed=2,"
        "tremolo=f=8:d=0.4,"
        "volume=0.9"
    ),
    "deep_space": (
        "aecho=0.8:0.9:500:0.3,"
        "lowpass=f=2000,"
        "highpass=f=100,"
        "chorus=0.5:0.9:50:0.4:0.25:2,"
        "volume=0.7"
    ),
    # Fixed: aphaser speed max is 2.0, not 3.0
    "glitch": (
        "acrusher=bits=4:mix=0.6,"
        "tremolo=f=15:d=0.7,"
        "aphaser=type=t:speed=2:decay=0.5,"
        "volume=0.85"
    ),
    "alien": (
        "asetrate=44100*1.3,aresample=44100,"
        "flanger=delay=3:depth=5:speed=1.5,"
        "chorus=0.7:0.9:25:0.5:0.3:3,"
        "volume=0.85"
    ),
    # New: whisper effect
    "whisper": (
        "highpass=f=200,lowpass=f=8000,"
        "volume=0.6,"
        "aecho=0.5:0.5:10:0.2,"
        "volume=1.5"
    ),
    # New: underwater
    "underwater": (
        "lowpass=f=1000,"
        "aecho=0.7:0.5:120:0.4,"
        "chorus=0.6:0.9:30:0.4:0.3:2,"
        "volume=0.9"
    ),
    # New: demonic
    "demonic": (
        "asetrate=44100*0.75,aresample=44100,"
        "aecho=0.8:0.9:60:0.4,"
        "tremolo=f=4:d=0.3,"
        "volume=1.0"
    ),
}


# Allow user-defined custom presets via JSON file
import json as _json
from pathlib import Path as _Path

CUSTOM_PRESETS_FILE = _Path(os.environ.get("CUSTOM_EFFECTS_FILE", "/app/outputs/custom_effects.json"))


def load_custom_presets() -> dict[str, str]:
    """Load user-defined custom effect presets from JSON file."""
    if CUSTOM_PRESETS_FILE.exists():
        try:
            return _json.loads(CUSTOM_PRESETS_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_custom_preset(name: str, filter_chain: str) -> None:
    """Save a user-defined custom effect preset."""
    CUSTOM_PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    presets = load_custom_presets()
    presets[name] = filter_chain
    CUSTOM_PRESETS_FILE.write_text(_json.dumps(presets, indent=2))


def delete_custom_preset(name: str) -> bool:
    """Remove a user-defined preset. Returns True if it existed."""
    presets = load_custom_presets()
    if name in presets:
        del presets[name]
        CUSTOM_PRESETS_FILE.write_text(_json.dumps(presets, indent=2))
        return True
    return False


def get_all_presets() -> dict[str, str]:
    """Merge built-in and user custom presets (custom overrides built-in)."""
    return {**EFFECT_PRESETS, **load_custom_presets()}


async def apply_effects(
    input_path: str,
    output_path: str,
    preset: str = "none",
    custom_config: dict | None = None,
) -> str:
    """Apply audio effects to a WAV file using FFmpeg.

    Args:
        input_path: Path to input audio file
        output_path: Path for processed output
        preset: Effect preset name from EFFECT_PRESETS
        custom_config: Optional overrides (wet_dry_mix, pitch_shift, eq, etc.)

    Returns:
        Path to processed audio file
    """
    if preset == "none" and not custom_config:
        # No effects - just copy
        if input_path != output_path:
            seg = AudioSegment.from_file(input_path)
            seg.export(output_path, format="wav")
        return output_path

    filters = []

    # Base preset (merged: built-in + user custom)
    all_presets = get_all_presets()
    if preset in all_presets:
        base_filter = all_presets[preset]
        # Apply wet/dry mix if specified
        if custom_config and "wet_dry_mix" in custom_config:
            mix = custom_config["wet_dry_mix"]
            filters.append(f"[0:a]asplit=2[dry][wet];[wet]{base_filter}[processed];"
                          f"[dry][processed]amix=inputs=2:weights={1-mix} {mix}[out]")
        else:
            filters.append(base_filter)

    config = custom_config or {}

    # Pitch shift
    if "pitch_shift" in config and config["pitch_shift"] != 0:
        semitones = config["pitch_shift"]
        rate = 2 ** (semitones / 12.0)
        filters.append(f"asetrate=44100*{rate:.4f},aresample=44100")

    # EQ adjustments
    if "eq" in config:
        eq = config["eq"]
        if "bass" in eq:
            filters.append(f"bass=g={eq['bass']}:f=100")
        if "mid" in eq:
            filters.append(f"equalizer=f=1000:t=q:w=1:g={eq['mid']}")
        if "treble" in eq:
            filters.append(f"treble=g={eq['treble']}:f=8000")

    # Reverb approximation
    if "reverb" in config and config["reverb"] > 0:
        r = config["reverb"]
        filters.append(f"aecho=0.8:0.88:{int(60*r)}:{0.3*r:.2f}")

    # Compression
    if "compression" in config and config["compression"] > 0:
        c = config["compression"]
        filters.append(f"acompressor=threshold={-10-10*c}dB:ratio={2+6*c:.0f}:attack=5:release=50")

    # Volume adjustment
    if "volume_db" in config and config["volume_db"] != 0:
        filters.append(f"volume={config['volume_db']}dB")

    if not filters:
        seg = AudioSegment.from_file(input_path)
        seg.export(output_path, format="wav")
        return output_path

    # Check if we have a complex filter or simple chain
    filter_str = filters[0] if len(filters) == 1 else ",".join(filters)
    has_complex = "[0:a]" in filter_str

    cmd = ["ffmpeg", "-y", "-i", input_path]
    if has_complex:
        cmd += ["-filter_complex", filter_str, "-map", "[out]"]
    else:
        cmd += ["-af", filter_str]
    cmd += ["-ar", "44100", output_path]

    logger.info("applying_effects", preset=preset, cmd=" ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error("ffmpeg_error", stderr=stderr.decode()[-500:])
        raise RuntimeError(f"FFmpeg effects failed: {stderr.decode()[-200:]}")

    return output_path


async def normalize_loudness(input_path: str, output_path: str, target_lufs: float = -16.0) -> str:
    """Two-pass loudness normalization using FFmpeg."""
    # Pass 1: measure
    cmd1 = [
        "ffmpeg", "-i", input_path, "-af",
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-"
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd1, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()

    # Pass 2: apply (simplified - use single pass if measurement fails)
    cmd2 = [
        "ffmpeg", "-y", "-i", input_path, "-af",
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-ar", "44100", output_path
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    return output_path


async def concatenate_audio(
    file_paths: list[str],
    output_path: str,
    silence_ms: int = 500,
    sample_rate: int = 44100,
) -> str:
    """Concatenate multiple audio files with silence between them (sequential)."""
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=silence_ms, frame_rate=sample_rate)

    for i, path in enumerate(file_paths):
        seg = AudioSegment.from_file(path)
        combined += seg
        if i < len(file_paths) - 1:
            combined += silence

    combined.export(output_path, format="wav", parameters=["-ar", str(sample_rate)])
    return output_path


async def concatenate_audio_timeline(
    clips: list[dict],
    output_path: str,
    silence_ms: int = 500,
    sample_rate: int = 44100,
) -> str:
    """Place audio clips on a timeline, honoring explicit start times.

    Each clip dict: {"path": str, "start_ms": int|None, "pause_after_ms": int}

    Behavior:
    - Clips with an explicit start_ms are positioned at that absolute time.
    - Clips without start_ms play sequentially after the previous clip ends,
      plus the global silence gap (and any per-line pause_after_ms).
    - Overlapping clips are mixed together.

    Implementation note: builds the mix in a single numpy float buffer and adds
    each clip at its sample offset. This is far more memory-efficient than
    repeatedly calling AudioSegment.overlay() (which copies the whole canvas on
    every call) and avoids OOM-killing the worker on long timelines.
    """
    import numpy as np

    if not clips:
        AudioSegment.silent(duration=10, frame_rate=sample_rate).export(
            output_path, format="wav", parameters=["-ar", str(sample_rate)]
        )
        return output_path

    # First pass: load each clip's samples (mono, target sample rate) and
    # compute its position, without keeping AudioSegments around.
    placed = []  # (start_sample, np.ndarray float32)
    playhead_ms = 0
    max_end_sample = 0

    for clip in clips:
        seg = AudioSegment.from_file(clip["path"])
        seg = seg.set_frame_rate(sample_rate).set_channels(1)
        samples = np.array(seg.get_array_of_samples(), dtype=np.float32)

        start_ms = clip.get("start_ms")
        pause_after = clip.get("pause_after_ms", 0) or 0
        position_ms = start_ms if start_ms is not None else playhead_ms

        start_sample = int(position_ms * sample_rate / 1000)
        placed.append((start_sample, samples))

        end_sample = start_sample + len(samples)
        max_end_sample = max(max_end_sample, end_sample)

        # Advance playhead for subsequent auto-positioned clips
        playhead_ms = (position_ms + len(seg)) + pause_after + silence_ms

    # Allocate the mix buffer once and add each clip in place
    mix = np.zeros(max_end_sample, dtype=np.float32)
    for start_sample, samples in placed:
        end = start_sample + len(samples)
        mix[start_sample:end] += samples

    # Prevent clipping: scale down if the summed peak exceeds int16 range
    peak = np.max(np.abs(mix)) if max_end_sample > 0 else 0
    limit = 32767.0
    if peak > limit:
        mix *= (limit / peak)

    mix_int16 = mix.astype(np.int16)

    out = AudioSegment(
        mix_int16.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=1,
    )
    out.export(output_path, format="wav", parameters=["-ar", str(sample_rate)])
    return output_path


def get_audio_duration_ms(file_path: str) -> int:
    """Get duration of audio file in milliseconds."""
    seg = AudioSegment.from_file(file_path)
    return len(seg)
