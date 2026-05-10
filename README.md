# DialogueForge

A production-ready full-stack application for generating character dialogue audio using the ElevenLabs Text-to-Speech API.

## Features

- **Script Import**: CSV, TXT, and JSON dialogue script parsing
- **Voice Assignment**: Per-character ElevenLabs voice/model configuration
- **Audio Effects**: Radio, helmet, robot, telephone, and more via FFmpeg
- **Batch Generation**: Concurrent TTS with rate limiting and retry
- **Smart Caching**: Avoid duplicate API calls via content hashing
- **Export Options**: Combined WAV, individual files, ZIP archives
- **Timeline Editor**: Drag-and-drop dialogue arrangement
- **Project Save/Load**: Persist all settings as .projectforge files
- **Cost Estimation**: Pre-generation credit usage estimates
- **Real-time Logs**: Live WebSocket generation status

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env and add your ElevenLabs API key (or add via GUI)

# 2. Launch
docker compose up --build

# 3. Open
# http://localhost
```

## Architecture

| Service   | Port | Description              |
|-----------|------|--------------------------|
| Frontend  | 3000 | React + TypeScript + Vite|
| Backend   | 8000 | FastAPI + Uvicorn        |
| Redis     | 6379 | Job queue + caching      |
| PostgreSQL| 5432 | Project/voice storage    |
| Nginx     | 80   | Reverse proxy            |

## Sample Data

A sample CSV is included at `samples/demo_script.csv`.

## API Endpoints

| Method | Path                  | Description              |
|--------|----------------------|--------------------------|
| POST   | /api/scripts/upload  | Upload dialogue script   |
| GET    | /api/scripts/{id}    | Get parsed script        |
| POST   | /api/generate        | Start batch generation   |
| GET    | /api/jobs/{id}       | Job status               |
| GET    | /api/voices          | List available voices    |
| POST   | /api/voices/sync     | Sync from ElevenLabs     |
| POST   | /api/effects/preview | Preview audio effect     |
| POST   | /api/projects/save   | Save project             |
| POST   | /api/projects/load   | Load project             |
| GET    | /api/export/{job_id} | Download generated audio |

## Environment Variables

See `.env.example` for all configuration options.
