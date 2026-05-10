"""Generation job management routes."""

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.database import GenerationJob, LineResult, JobStatus, Project
from app.schemas import GenerationRequest, GenerationJobResponse, CostEstimate
from app.services.generation import GenerationService
from app.api.routes.voices import _get_api_key

router = APIRouter(tags=["generation"])


@router.post("/generate", response_model=GenerationJobResponse)
async def start_generation(req: GenerationRequest, db: AsyncSession = Depends(get_db)):
    """Start a dialogue generation job."""
    api_key = await _get_api_key(db)
    if not api_key:
        raise HTTPException(400, "No ElevenLabs API key configured. Add one in Settings.")

    # Create job record
    job = GenerationJob(
        project_id=req.project_id,
        export_mode=req.export_mode,
        output_format=req.output_format,
        settings={
            "silence_between_ms": req.silence_between_ms,
            "normalize": req.normalize,
        },
    )
    db.add(job)
    await db.flush()

    # Dispatch to Celery
    from app.workers.celery_worker import generate_dialogue_task
    generate_dialogue_task.delay(
        job_id=str(job.id),
        script_id=str(req.script_id),
        project_id=str(req.project_id),
        export_mode=req.export_mode,
        output_format=req.output_format,
        silence_ms=req.silence_between_ms,
        normalize=req.normalize,
        line_ids=[str(lid) for lid in req.line_ids] if req.line_ids else None,
        api_key=api_key,
    )

    return GenerationJobResponse(
        job_id=job.id,
        status=job.status.value,
        total_lines=job.total_lines,
        completed_lines=0,
        failed_lines=0,
        created_at=job.created_at,
    )


@router.get("/jobs/{job_id}", response_model=GenerationJobResponse)
async def get_job_status(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get the status of a generation job."""
    job = (await db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )).scalar_one_or_none()

    if not job:
        raise HTTPException(404, "Job not found")

    return GenerationJobResponse(
        job_id=job.id,
        status=job.status.value,
        total_lines=job.total_lines,
        completed_lines=job.completed_lines,
        failed_lines=job.failed_lines,
        created_at=job.created_at,
    )


@router.get("/jobs/{job_id}/lines")
async def get_job_lines(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get detailed per-line results for a job."""
    results = (await db.execute(
        select(LineResult).where(LineResult.job_id == job_id).order_by(LineResult.created_at)
    )).scalars().all()

    return [
        {
            "id": str(r.id),
            "line_id": str(r.line_id),
            "status": r.status.value,
            "duration_ms": r.duration_ms,
            "character_count": r.character_count,
            "error_message": r.error_message,
            "has_audio": bool(r.processed_path and os.path.exists(r.processed_path)),
        }
        for r in results
    ]


@router.get("/export/{job_id}")
async def export_audio(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Download generated audio output."""
    job = (await db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )).scalar_one_or_none()

    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(400, f"Job is {job.status.value}, not completed")
    if not job.output_path or not os.path.exists(job.output_path):
        raise HTTPException(404, "Output file not found")

    if os.path.isfile(job.output_path):
        filename = os.path.basename(job.output_path)
        media_type = "audio/wav" if filename.endswith(".wav") else "application/zip"
        return FileResponse(job.output_path, filename=filename, media_type=media_type)

    raise HTTPException(400, "Individual file export — download files from job lines endpoint")


@router.post("/estimate", response_model=CostEstimate)
async def estimate_cost(req: GenerationRequest, db: AsyncSession = Depends(get_db)):
    """Estimate generation cost before running."""
    api_key = await _get_api_key(db)
    service = GenerationService(db, api_key)
    result = await service.estimate_cost(req.script_id, req.project_id)
    return CostEstimate(**result)


@router.get("/jobs")
async def list_jobs(project_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)):
    """List generation jobs."""
    query = select(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(50)
    if project_id:
        query = query.where(GenerationJob.project_id == project_id)
    jobs = (await db.execute(query)).scalars().all()

    return [
        GenerationJobResponse(
            job_id=j.id,
            status=j.status.value,
            total_lines=j.total_lines,
            completed_lines=j.completed_lines,
            failed_lines=j.failed_lines,
            created_at=j.created_at,
        )
        for j in jobs
    ]
