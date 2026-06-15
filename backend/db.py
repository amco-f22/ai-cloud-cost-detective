"""
Database — PostgreSQL connection, table creation, and query functions.
Uses psycopg3 for synchronous operations with connection pooling.
"""

import os
import json
import logging
from datetime import datetime, timezone
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

# Connection pool (initialized on first use)
_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL not set. Example: postgresql://user:pass@localhost:5432/cost_detective"
            )
        _pool = ConnectionPool(database_url, min_size=1, max_size=10)
        logger.info("Database connection pool created")
    return _pool


@contextmanager
def get_connection():
    """Context manager for database connections from the pool."""
    p = _get_pool()
    with p.connection() as conn:
        yield conn


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    region VARCHAR(50) NOT NULL,
                    resources_scanned INTEGER DEFAULT 0,
                    issues_found INTEGER DEFAULT 0,
                    estimated_savings VARCHAR(100) DEFAULT '',
                    analysis_result JSONB,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC);
            """)
        conn.commit()
    logger.info("Database tables initialized")


# ─── User operations ───

def create_user(email: str, password_hash: str) -> dict:
    """Create a new user and return user dict."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email, created_at",
                (email, password_hash),
            )
            result = cur.fetchone()
            conn.commit()
            return dict(result)


def get_user_by_email(email: str) -> dict | None:
    """Find a user by email."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, email, password_hash, created_at FROM users WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


# ─── Analysis operations ───

def create_analysis(user_id: int, region: str) -> int:
    """Create a pending analysis record and return its ID."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO analyses (user_id, region, status)
                   VALUES (%s, %s, 'pending') RETURNING id""",
                (user_id, region),
            )
            result = cur.fetchone()[0]
            conn.commit()
            return result


def update_analysis(
    analysis_id: int,
    resources_scanned: int,
    issues_found: int,
    estimated_savings: str,
    analysis_result: dict,
    status: str = "completed",
):
    """Update an analysis record with results."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE analyses
                   SET resources_scanned = %s,
                       issues_found = %s,
                       estimated_savings = %s,
                       analysis_result = %s,
                       status = %s
                   WHERE id = %s""",
                (
                    resources_scanned,
                    issues_found,
                    estimated_savings,
                    Jsonb(analysis_result),
                    status,
                    analysis_id,
                ),
            )
        conn.commit()


def get_user_analyses(user_id: int, limit: int = 50) -> list[dict]:
    """Get analysis history for a user."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT id, region, resources_scanned, issues_found,
                          estimated_savings, status, created_at
                   FROM analyses
                   WHERE user_id = %s
                   ORDER BY created_at DESC
                   LIMIT %s""",
                (user_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]


def get_analysis_by_id(analysis_id: int, user_id: int) -> dict | None:
    """Get a specific analysis result."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT id, region, resources_scanned, issues_found,
                          estimated_savings, analysis_result, status, created_at
                   FROM analyses
                   WHERE id = %s AND user_id = %s""",
                (analysis_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def close_pool():
    """Close the connection pool on shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("Database connection pool closed")
