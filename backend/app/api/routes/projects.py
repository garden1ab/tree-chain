"""Project save/load and management routes."""

import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.database import Project, Script, DialogueLine, CharacterVoiceConfig
from app.schemas import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=ProjectResponse)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """Create a new project."""
    project = Project(name=body.name, description=body.description)
    db.add(project)
    await db.flush()
    return ProjectResponse.model_validate(project)


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects."""
    projects = (await db.execute(
        select(Project).order_by(Project.updated_at.desc())
    )).scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get project details."""
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return ProjectResponse.model_validate(project)


@router.post("/save/{project_id}")
async def save_project_file(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Export project as .projectforge JSON."""
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    # Gather data
    scripts = (await db.execute(
        select(Script).where(Script.project_id == project_id).options(selectinload(Script.lines))
    )).scalars().all()

    configs = (await db.execute(
        select(CharacterVoiceConfig).where(CharacterVoiceConfig.project_id == project_id)
    )).scalars().all()

    export_data = {
        "version": "1.0",
        "project": {
            "name": project.name,
            "description": project.description,
            "settings": project.settings or {},
        },
        "scripts": [
            {
                "filename": s.filename,
                "lines": [
                    {
                        "line_number": l.line_number,
                        "character_name": l.character_name,
                        "text": l.text,
                        "raw_text": l.raw_text,
                        "directives": l.directives,
                        "pause_after_ms": l.pause_after_ms,
                    }
                    for l in sorted(s.lines, key=lambda x: x.line_number)
                ],
            }
            for s in scripts
        ],
        "character_configs": [
            {
                "character_name": c.character_name,
                "voice_id": c.voice_id,
                "model_id": c.model_id,
                "stability": c.stability,
                "similarity_boost": c.similarity_boost,
                "style": c.style,
                "use_speaker_boost": c.use_speaker_boost,
                "effects_preset": c.effects_preset,
                "effects_config": c.effects_config or {},
                "volume_adjustment": c.volume_adjustment,
            }
            for c in configs
        ],
    }

    return JSONResponse(content=export_data, headers={
        "Content-Disposition": f'attachment; filename="{project.name}.projectforge"'
    })


@router.post("/load")
async def load_project_file(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Import a .projectforge file."""
    content = (await file.read()).decode('utf-8')
    data = json.loads(content)

    # Create project
    proj_data = data.get("project", {})
    project = Project(
        name=proj_data.get("name", "Imported Project"),
        description=proj_data.get("description", ""),
        settings=proj_data.get("settings", {}),
    )
    db.add(project)
    await db.flush()

    # Import scripts
    for script_data in data.get("scripts", []):
        script = Script(project_id=project.id, filename=script_data.get("filename", "imported.csv"))
        db.add(script)
        await db.flush()

        for line_data in script_data.get("lines", []):
            db.add(DialogueLine(
                script_id=script.id,
                line_number=line_data["line_number"],
                character_name=line_data["character_name"],
                text=line_data["text"],
                raw_text=line_data.get("raw_text", line_data["text"]),
                directives=line_data.get("directives", []),
                pause_after_ms=line_data.get("pause_after_ms", 0),
            ))

    # Import configs
    for cfg_data in data.get("character_configs", []):
        db.add(CharacterVoiceConfig(
            project_id=project.id,
            character_name=cfg_data["character_name"],
            voice_id=cfg_data.get("voice_id", ""),
            model_id=cfg_data.get("model_id", "eleven_multilingual_v2"),
            stability=cfg_data.get("stability", 0.5),
            similarity_boost=cfg_data.get("similarity_boost", 0.75),
            style=cfg_data.get("style", 0.0),
            use_speaker_boost=cfg_data.get("use_speaker_boost", True),
            effects_preset=cfg_data.get("effects_preset", "none"),
            effects_config=cfg_data.get("effects_config", {}),
            volume_adjustment=cfg_data.get("volume_adjustment", 0.0),
        ))

    await db.flush()
    return ProjectResponse.model_validate(project)
