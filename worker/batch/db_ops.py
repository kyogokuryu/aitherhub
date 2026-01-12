"""
Database operations for batch worker.
Provides synchronous wrappers around async SQLAlchemy operations.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in environment")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Global event loop for reuse (avoids asyncpg pool conflicts)
_loop = None


def get_event_loop():
    """Get or create a persistent event loop for DB operations."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


@asynccontextmanager
async def get_session():
    """Async context manager for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database connection (test connectivity)."""
    async with get_session() as session:
        await session.execute("SELECT 1")
    print("[DB] Database connection initialized successfully")


async def close_db():
    """Close database engine and cleanup."""
    await engine.dispose()
    print("[DB] Database connection closed")


def init_db_sync():
    """Synchronous wrapper for database initialization."""
    loop = get_event_loop()
    loop.run_until_complete(init_db())


def close_db_sync():
    """Synchronous wrapper for database cleanup."""
    loop = get_event_loop()
    loop.run_until_complete(close_db())


from sqlalchemy import text


async def insert_phase(
    video_id: str,
    phase_index: int,
    phase_description: str | None,
    time_start: float | None,
    time_end: float | None,
    view_start: int | None,
    view_end: int | None,
    like_start: int | None,
    like_end: int | None,
    delta_view: int | None,
    delta_like: int | None,
    phase_group_id: int | None = None,
):
    """Insert a phase row and return the generated UUID as string."""
    sql = text(
        """
        INSERT INTO phases (
            video_id, phase_group_id, phase_index, phase_description,
            time_start, time_end, view_start, view_end,
            like_start, like_end, delta_view, delta_like
        ) VALUES (
            :video_id, :phase_group_id, :phase_index, :phase_description,
            :time_start, :time_end, :view_start, :view_end,
            :like_start, :like_end, :delta_view, :delta_like
        ) RETURNING id
        """
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(sql, {
            "video_id": video_id,
            "phase_group_id": phase_group_id,
            "phase_index": phase_index,
            "phase_description": phase_description,
            "time_start": time_start,
            "time_end": time_end,
            "view_start": view_start,
            "view_end": view_end,
            "like_start": like_start,
            "like_end": like_end,
            "delta_view": delta_view,
            "delta_like": delta_like,
        })
        row = result.fetchone()
        await session.commit()

    if row is None:
        raise RuntimeError("Failed to insert phase")

    # returned id is UUID object (if driver returns), convert to str
    return str(row[0])


def insert_phase_sync(*args, **kwargs):
    """Synchronous wrapper for `insert_phase` that returns the new id as string."""
    loop = get_event_loop()
    return loop.run_until_complete(insert_phase(*args, **kwargs))
