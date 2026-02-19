"""
Admin dashboard API endpoint.
Provides platform-wide statistics for the master dashboard.
Each query is independently wrapped so a single failure does not break the whole dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger
from typing import Optional

from app.core.dependencies import get_db, get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])

ADMIN_ID = "aither"
ADMIN_PASS = "hub"


async def _safe_query(db: AsyncSession, sql: str, default=0):
    """Execute a scalar query with full error isolation."""
    try:
        result = await db.execute(text(sql))
        val = result.scalar()
        return val if val is not None else default
    except Exception as e:
        logger.warning(f"Admin query failed [{sql[:60]}...]: {e}")
        try:
            await db.rollback()
        except Exception:
            pass
        return default


async def _get_dashboard_data(db: AsyncSession) -> dict:
    """Gather all dashboard statistics with per-query error isolation."""

    # ── Data Volume ──
    total_videos = await _safe_query(db, "SELECT COUNT(*) FROM videos")
    analyzed_videos = await _safe_query(
        db, "SELECT COUNT(*) FROM videos WHERE status = 'DONE'"
    )
    pending_videos = total_videos - analyzed_videos

    # Total video duration
    total_duration_seconds = await _safe_query(db, """
        SELECT COALESCE(SUM(max_sec), 0) FROM (
            SELECT video_id, MAX(
                CASE
                    WHEN time_end IS NOT NULL AND time_end != '' AND time_end LIKE '%%:%%:%%'
                    THEN CAST(SPLIT_PART(time_end, ':', 1) AS INTEGER) * 3600
                       + CAST(SPLIT_PART(time_end, ':', 2) AS INTEGER) * 60
                       + CAST(SPLIT_PART(SPLIT_PART(time_end, ':', 3), '.', 1) AS INTEGER)
                    ELSE 0
                END
            ) as max_sec
            FROM video_phases
            GROUP BY video_id
        ) sub
    """)
    total_duration_seconds = int(total_duration_seconds)

    # ── Video Types ──
    # Try upload_type column; if it doesn't exist, fall back
    screen_recording_count = await _safe_query(
        db,
        "SELECT COUNT(*) FROM videos WHERE upload_type = 'screen_recording' OR upload_type IS NULL",
    )
    clean_video_count = await _safe_query(
        db, "SELECT COUNT(*) FROM videos WHERE upload_type = 'clean_video'"
    )
    # If upload_type column doesn't exist, both will be 0; show total as screen_recording
    if screen_recording_count == 0 and clean_video_count == 0 and total_videos > 0:
        screen_recording_count = total_videos

    latest_upload_raw = await _safe_query(
        db, "SELECT MAX(created_at) FROM videos", default=None
    )
    latest_upload = str(latest_upload_raw) if latest_upload_raw else None

    # ── User Scale ──
    # Try is_active first, fall back to counting all users
    total_users = await _safe_query(
        db, "SELECT COUNT(*) FROM users WHERE is_active = true"
    )
    if total_users == 0:
        total_users = await _safe_query(db, "SELECT COUNT(*) FROM users")

    total_streamers = await _safe_query(
        db, "SELECT COUNT(DISTINCT user_id) FROM videos"
    )
    this_month_uploaders = await _safe_query(
        db,
        "SELECT COUNT(DISTINCT user_id) FROM videos "
        "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)",
    )

    # Format duration
    total_hours = total_duration_seconds // 3600
    total_minutes = (total_duration_seconds % 3600) // 60

    return {
        "data_volume": {
            "total_videos": total_videos,
            "analyzed_videos": analyzed_videos,
            "pending_videos": pending_videos,
            "total_duration_seconds": total_duration_seconds,
            "total_duration_display": f"{total_hours}時間{total_minutes}分",
        },
        "video_types": {
            "screen_recording_count": screen_recording_count,
            "clean_video_count": clean_video_count,
            "latest_upload": latest_upload,
        },
        "user_scale": {
            "total_users": total_users,
            "total_streamers": total_streamers,
            "this_month_uploaders": this_month_uploaders,
        },
    }


@router.get("/dashboard")
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """JWT auth, admin role required."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return await _get_dashboard_data(db)


@router.get("/debug-schema")
async def debug_schema(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Temporary debug endpoint to check actual DB schema."""
    expected_key = f"{ADMIN_ID}:{ADMIN_PASS}"
    if x_admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid admin credentials")
    results = {}
    for table in ["videos", "users", "video_phases"]:
        try:
            r = await db.execute(text(
                f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' ORDER BY ordinal_position"
            ))
            results[table] = [row[0] for row in r.fetchall()]
        except Exception as e:
            results[table] = f"Error: {e}"
    return results


@router.get("/dashboard-public")
async def get_dashboard_stats_public(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Simple ID:password auth via header."""
    expected_key = f"{ADMIN_ID}:{ADMIN_PASS}"
    if x_admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid admin credentials")
    return await _get_dashboard_data(db)
