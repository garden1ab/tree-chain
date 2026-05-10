"""Script upload, parsing, and management routes."""

import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.database import Script, DialogueLine, Project
from app.schemas import ScriptUploadResponse, DialogueLineSchema
from app.services.script_parser import parse_script

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.post("/upload", response_model=ScriptUploadResponse)
async def upload_script(
    file: UploadFile = File(...),
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload and parse a dialogue script file."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('csv', 'txt', 'json'):
        raise HTTPException(400, f"Unsupported file format: {ext}. Use .csv, .txt, or .json")

    content = (await file.read()).decode('utf-8', errors='replace')

    # Parse
    parsed_lines = parse_script(content, file.filename)
    if not parsed_lines:
        raise HTTPException(400, "No dialogue lines could be parsed from the file")

    # Create or use project
    if project_id:
        pid = uuid.UUID(project_id)
    else:
        project = Project(name=file.filename.rsplit('.', 1)[0])
        db.add(project)
        await db.flush()
        pid = project.id

    # Save script
    script = Script(project_id=pid, filename=file.filename, raw_content=content)
    db.add(script)
    await db.flush()

    # Save lines
    db_lines = []
    for pl in parsed_lines:
        dl = DialogueLine(
            script_id=script.id,
            line_number=pl.line_number,
            character_name=pl.character_name,
            text=pl.text,
            raw_text=pl.raw_text,
            directives=pl.directives,
            pause_after_ms=pl.pause_after_ms,
        )
        db.add(dl)
        db_lines.append(dl)

    await db.flush()

    characters = sorted(set(pl.character_name for pl in parsed_lines))

    return ScriptUploadResponse(
        script_id=script.id,
        filename=file.filename,
        total_lines=len(db_lines),
        characters=characters,
        lines=[DialogueLineSchema.model_validate(dl) for dl in db_lines],
    )


@router.get("/{script_id}")
async def get_script(script_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a parsed script with all dialogue lines."""
    script = (await db.execute(
        select(Script).where(Script.id == script_id).options(selectinload(Script.lines))
    )).scalar_one_or_none()

    if not script:
        raise HTTPException(404, "Script not found")

    lines = sorted(script.lines, key=lambda l: l.line_number)
    characters = sorted(set(l.character_name for l in lines))

    return {
        "script_id": str(script.id),
        "filename": script.filename,
        "total_lines": len(lines),
        "characters": characters,
        "lines": [DialogueLineSchema.model_validate(l) for l in lines],
    }
