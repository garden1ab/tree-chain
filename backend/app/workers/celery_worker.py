"""Celery worker for background generation jobs."""

import asyncio
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "dialogueforge",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_concurrency=2,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


@celery_app.task(bind=True, name="generate_dialogue")
def generate_dialogue_task(self, job_id: str, script_id: str, project_id: str,
                           export_mode: str, output_format: str, silence_ms: int,
                           normalize: bool, line_ids: list[str] | None, api_key: str | None):
    """Background task for dialogue generation."""
    import uuid
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.services.generation import GenerationService

    async def _run():
        # Create a fresh engine + session for this task's event loop
        # to avoid "attached to a different loop" errors
        task_engine = create_async_engine(
            settings.database_url, echo=False, pool_size=5, max_overflow=5
        )
        task_session_factory = async_sessionmaker(
            task_engine, class_=AsyncSession, expire_on_commit=False
        )

        try:
            async with task_session_factory() as db:
                service = GenerationService(db, api_key)
                await service.run_generation(
                    job_id=uuid.UUID(job_id),
                    script_id=uuid.UUID(script_id),
                    project_id=uuid.UUID(project_id),
                    export_mode=export_mode,
                    output_format=output_format,
                    silence_ms=silence_ms,
                    normalize=normalize,
                    line_ids=[uuid.UUID(lid) for lid in line_ids] if line_ids else None,
                )
        finally:
            await task_engine.dispose()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


if __name__ == "__main__":
    celery_app.worker_main(["worker", "--loglevel=info", "--concurrency=2"])
