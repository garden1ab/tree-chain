# DialogueForge

A production-ready full-stack application for generating character dialogue audio with multiple TTS engines — cloud (ElevenLabs) and local (Kokoro, Piper, Chatterbox, XTTS v2, Orpheus).

## Features

- **Multi-Provider TTS**: Mix ElevenLabs, Kokoro, Chatterbox, XTTS v2, Orpheus, and Piper — each character can use a different engine
- **Script Import**: CSV, TXT, and JSON dialogue script parsing
- **Voice Assignment**: Per-character voice/model configuration with manual voice ID input
- **Audio Effects**: Radio, helmet, robot, telephone, and more via FFmpeg
- **Batch Generation**: Concurrent TTS with rate limiting and retry
- **Smart Caching**: Avoid duplicate API/generation calls via content hashing
- **Export Options**: Combined WAV, individual files, ZIP archives
- **Project Save/Load**: Persist all settings as .projectforge files
- **Cost Estimation**: Pre-generation credit usage estimates
- **Real-time Logs**: Live generation status

## Quick Start (ElevenLabs only)

```bash
cp .env.example .env        # Edit and add your ElevenLabs API key
docker compose up --build    # Start core services
# Open http://localhost
```

## Quick Start (with GPU models)

```bash
cp .env.example .env
docker compose --profile gpu up --build   # Starts Chatterbox, XTTS, Orpheus sidecars
# Open http://localhost
```

You can also start individual GPU services:

```bash
docker compose up --build chatterbox   # Just Chatterbox
docker compose up --build xtts         # Just XTTS v2
docker compose up --build orpheus      # Just Orpheus
```

## Architecture

```
                    ┌──────────────┐     ┌──────────────┐
   Browser ───────▶│    Nginx     │────▶│   Frontend   │
                    │   (port 80)  │     │  React/Vite  │
                    └──────┬───────┘     └──────────────┘
                           │
                    ┌──────▼───────┐     ┌──────────────┐
                    │   Backend    │────▶│  PostgreSQL   │
                    │   FastAPI    │     └──────────────┘
                    └──────┬───────┘     ┌──────────────┐
                           │        ────▶│    Redis      │
                    ┌──────▼───────┐     └──────────────┘
                    │   Worker     │
                    │   Celery     │
                    └──┬───┬───┬───┘
                       │   │   │
          ┌────────────┘   │   └────────────┐
          ▼                ▼                ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
   │ Chatterbox  │ │   XTTS v2   │ │  Orpheus    │
   │  (GPU)      │ │   (GPU)     │ │  (GPU)      │
   └─────────────┘ └─────────────┘ └─────────────┘
```

### TTS Providers

| Provider | Type | GPU? | Best for |
|----------|------|------|----------|
| **ElevenLabs** | Cloud API | No | Highest quality, production |
| **Kokoro** | In-process | No (CPU) | Fast, lightweight, free |
| **Piper** | In-process | No (CPU) | Ultra-fast, low resource |
| **Chatterbox** | Sidecar | Recommended | Expressive, voice cloning |
| **XTTS v2** | Sidecar | Recommended | Voice cloning, multilingual |
| **Orpheus** | Sidecar | Yes | Emotional control |

### GPU Sidecars (optional)

| Service     | Model Size | VRAM  |
|-------------|------------|-------|
| Chatterbox  | ~350M      | ~2GB  |
| XTTS v2     | ~1.5B      | ~4GB  |
| Orpheus     | ~3B        | ~8GB  |

## Remote Access

To access from another computer on your network, change the nginx port in `docker-compose.yml`:

```yaml
nginx:
  ports:
    - "8080:80"
```

On Windows/WSL2, allow through firewall (Admin PowerShell):

```powershell
netsh advfirewall firewall add rule name="DialogueForge" dir=in action=allow protocol=TCP localport=8080
```

## Sample Data

Sample scripts are included in `samples/` (CSV, TXT, JSON formats).

## Environment Variables

See `.env.example` for all configuration options.
