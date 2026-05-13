"""Database engine and session factory."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.core.config import get_settings
from app.models.database import Base

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False, pool_size=10, max_overflow=20)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables and types, handling concurrent worker startup gracefully."""
    from sqlalchemy.exc import IntegrityError, ProgrammingError
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (IntegrityError, ProgrammingError) as e:
        if "already exists" in str(e):
            pass
        else:
            raise

    # Lightweight migration: add tts_provider column if missing
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE character_voice_configs ADD COLUMN IF NOT EXISTS tts_provider VARCHAR(50) DEFAULT 'elevenlabs'"
            ))
    except Exception:
        pass  # Column already exists or table doesn't exist yet
