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

    # Lightweight migrations: add new columns if missing
    migrations = [
        "ALTER TABLE character_voice_configs ADD COLUMN IF NOT EXISTS tts_provider VARCHAR(50) DEFAULT 'elevenlabs'",
        "ALTER TABLE character_voice_configs ADD COLUMN IF NOT EXISTS exaggeration FLOAT DEFAULT 0.5",
        "ALTER TABLE character_voice_configs ADD COLUMN IF NOT EXISTS cfg_weight FLOAT DEFAULT 0.5",
        "ALTER TABLE character_voice_configs ADD COLUMN IF NOT EXISTS temperature FLOAT DEFAULT 0.8",
        "ALTER TABLE character_voice_configs ADD COLUMN IF NOT EXISTS seed INTEGER DEFAULT 0",
        "ALTER TABLE character_voice_configs ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en'",
        "ALTER TABLE character_voice_configs ADD COLUMN IF NOT EXISTS el_voice_id VARCHAR(255) DEFAULT ''",
        "ALTER TABLE character_voice_configs ADD COLUMN IF NOT EXISTS cb_voice_id VARCHAR(255) DEFAULT ''",
        "ALTER TABLE dialogue_lines ADD COLUMN IF NOT EXISTS start_time_ms INTEGER",
        "ALTER TABLE dialogue_lines ADD COLUMN IF NOT EXISTS volume_adjust_db FLOAT DEFAULT 0.0",
        "ALTER TABLE dialogue_lines ADD COLUMN IF NOT EXISTS effect_override VARCHAR(100) DEFAULT ''",
    ]
    for sql in migrations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
        except Exception:
            pass
