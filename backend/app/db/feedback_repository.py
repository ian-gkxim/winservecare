"""Data access layer for Journey Feedback entities."""

from backend.app.db.database import get_db


async def insert_feedback(
    journey_id: int,
    carer_id: int,
    rating: str,
    comment: str | None,
    submitted_at: str,
) -> dict:
    """Insert a new feedback record. Returns the created row as a dict."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO journey_feedback (journey_id, carer_id, rating, comment, submitted_at)
               VALUES (?, ?, ?, ?, ?)""",
            (journey_id, carer_id, rating, comment, submitted_at),
        )
        await db.commit()
        new_cursor = await db.execute(
            "SELECT * FROM journey_feedback WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def get_feedback_by_journey(journey_id: int) -> dict | None:
    """Get feedback for a specific journey. Returns dict or None."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM journey_feedback WHERE journey_id = ?", (journey_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def feedback_exists(journey_id: int, carer_id: int) -> bool:
    """Check if feedback already exists for a journey+carer pair."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT 1 FROM journey_feedback WHERE journey_id = ? AND carer_id = ?",
            (journey_id, carer_id),
        )
        return await cursor.fetchone() is not None
