# DialogueForge

Generate character dialogue audio with multiple TTS engines — ElevenLabs (cloud), Chatterbox, Orpheus, Kokoro (local).

## Quick Start

```bash
# 1. Start DialogueForge
cp .env.example .env
docker compose up --build -d
# Open http://localhost

# 2. Start TTS engines (separate terminal)
cd tts-engines
./start.sh kokoro          # CPU-friendly, starts fast
# OR
./start.sh chatterbox      # Best quality (needs GPU)
# OR
./start.sh orpheus         # Emotion control (needs GPU)
# OR
./start.sh                 # All engines
```

## Architecture

```
┌─────────────┐       ┌───────────────────────────┐
│   Browser   │──────▶│  DialogueForge (port 80)  │
│             │       │  Nginx → Frontend/Backend  │
└─────────────┘       └───────────┬───────────────┘
                                  │ HTTP calls to TTS engines
                    ┌─────────────┼─────────────┐
                    ▼             ▼              ▼
             ┌─────────┐  ┌──────────┐  ┌──────────┐
             │ Kokoro   │  │Chatterbox│  │ Orpheus  │
             │ :8880    │  │  :4123   │  │  :8899   │
             │ (CPU)    │  │  (GPU)   │  │  (GPU)   │
             └─────────┘  └──────────┘  └──────────┘
```

DialogueForge and TTS engines run as **separate docker-compose stacks**. This means:
- DialogueForge starts instantly (no model downloads blocking startup)
- Each TTS engine has its own Web UI for testing voices directly
- You only run the engines you need
- Engines can run on different machines

## TTS Engines

| Engine | Quality | Voice Cloning | GPU Required | Web UI |
|--------|---------|---------------|-------------|--------|
| **Chatterbox** | ★★★★★ | ✅ 5-sec clips | Recommended | http://localhost:4123 |
| **Orpheus** | ★★★★☆ | ✅ Zero-shot | Yes | http://localhost:8899 |
| **Kokoro** | ★★★★☆ | ❌ | No (CPU) | http://localhost:8880 |
| **ElevenLabs** | ★★★★★ | ✅ | No | Cloud API |

### Chatterbox (Recommended)
- Beats ElevenLabs in blind tests (63.75% preference)
- Voice cloning from 5 seconds of audio
- Emotion/exaggeration control (0.0–2.0 slider)
- Multilingual (23 languages with Chatterbox Multilingual)
- ~5-7GB VRAM

### Orpheus
- Built on Llama 3B — LLM-quality speech understanding
- Emotion tags: `[laughs]`, `[sighs]`, `[chuckles]`, `[gasps]`
- 8 built-in voices, 8 languages
- Zero-shot voice cloning
- ~8GB VRAM

### Kokoro
- 82M parameters — runs on CPU
- 26 built-in voices (US/British, male/female)
- Fastest inference (~0.3s for any length)
- No voice cloning
- Highest MOS score (4.5) in benchmarks

## Features

- **Multi-Provider TTS**: Each character can use a different engine
- **Script Import**: CSV, TXT, JSON dialogue parsing
- **Voice Assignment**: Per-character voice/model configuration
- **Audio Effects**: Radio, helmet, robot, telephone, etc.
- **Batch Generation**: Concurrent TTS with rate limiting
- **Smart Caching**: Content-hash deduplication
- **Export**: Combined WAV, individual files, ZIP
- **Project Save/Load**: .projectforge files
- **No API key required** for local engines

## Configuration

Set TTS engine URLs in `.env` or the defaults will try `host.docker.internal`:

```env
CHATTERBOX_URL=http://host.docker.internal:4123
ORPHEUS_URL=http://host.docker.internal:8899
KOKORO_URL=http://host.docker.internal:8880
```

If running on Linux (where `host.docker.internal` doesn't work by default), use your machine's IP or add `extra_hosts` to docker-compose.yml.

## Sample Data

Sample scripts in `samples/` (CSV, TXT, JSON).

## Script Format

**CSV** — required columns `Character` and `Dialogue`, plus optional columns (any order, case-insensitive):

```csv
Character,Dialogue,Start,Pause,Volume,Effect,ElevenLabs,Chatterbox
Commander,"All units move in.",0:00,,0,radio,21m00Tcm4TlvDq8ikWAM,
Pilot,"Bandits at twelve o'clock!",0:04,,2,helmet,,my_pilot_clone
Operator,"Target is down.",0:08,1.5,-2,,EXAVITQu4vr4xnSDxMaL,
```

- **Start** — absolute placement on the combined timeline in `M:SS` format (e.g. `0:00`, `1:23`, `0:02.5`). When any line has a Start time, the combined export places clips at those exact times instead of back-to-back, leaving silence in the gaps. Lines without a Start time fall back to sequential placement.
- **Pause** — seconds of silence after the line (e.g. `1.5` or `0:02`).
- **Volume** — per-line volume adjustment in dB (e.g. `-3`, `2.5`). Added on top of the character's volume setting.
- **Effect** — per-line effect preset override (e.g. `radio`, `glitch`). Overrides the character's default effect for that line.
- **ElevenLabs** — the ElevenLabs voice_id to assign to this character. On upload, the character is auto-configured to use ElevenLabs with this voice.
- **Chatterbox** — the Chatterbox voice name (a cloned voice from the library, or `default`) to assign to this character. Used if no ElevenLabs voice is given.

Voice columns auto-populate the Character Voices tab on upload — no manual assignment needed. You can also click **Auto: ElevenLabs** or **Auto: Chatterbox** on that tab to round-robin assign voices to every character at once.

**TXT** — `Character: Dialogue`, with an optional leading timecode:
```
[0:15] Commander: All units move in.
Pilot: Bandits at twelve o'clock!
```

**JSON** — array of objects with keys `character`, `dialogue`, and optional `start`, `pause`, `volume`, `effect`.
