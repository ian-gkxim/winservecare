"""Async SQLite database connection management and schema initialisation."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

# Database file path: ./data/care_ops.db relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DB_DIR = _PROJECT_ROOT / "data"
DB_PATH = DB_DIR / "care_ops.db"

# Schema file path
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


async def init_db() -> None:
    """Initialise the database: create directory, apply schema if tables don't exist.

    Uses CREATE TABLE IF NOT EXISTS statements so existing data is preserved
    on subsequent application starts. Seeds mock data on first run.
    """
    # Ensure the data directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)

    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Enable WAL mode for better concurrent read performance
        await db.execute("PRAGMA journal_mode=WAL")
        # Enable foreign key enforcement
        await db.execute("PRAGMA foreign_keys=ON")
        # Execute the schema (all statements use IF NOT EXISTS)
        await db.executescript(schema_sql)
        await db.commit()

    # Seed mock data if tables are empty (first start)
    from backend.app.db.seed import seed_db

    await seed_db()


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager providing a database connection.

    Usage:
        async with get_db() as db:
            cursor = await db.execute("SELECT ...")
            rows = await cursor.fetchall()
    """
    db = await aiosqlite.connect(str(DB_PATH))
    try:
        # Enable foreign key enforcement per connection
        await db.execute("PRAGMA foreign_keys=ON")
        # Return rows as sqlite3.Row for dict-like access
        db.row_factory = aiosqlite.Row
        yield db
    finally:
        await db.close()
