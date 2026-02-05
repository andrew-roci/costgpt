"""Database connection management."""

import os
from contextlib import asynccontextmanager

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """Initialize the database connection pool."""
    global _pool
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)


async def close_db() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_db() -> asyncpg.Pool:
    """Get the database pool."""
    if not _pool:
        raise RuntimeError("Database not initialized")
    return _pool
