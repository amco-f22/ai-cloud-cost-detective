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
                    predicted_monthly_spend NUMERIC DEFAULT 0.0,
                    actual_monthly_spend NUMERIC DEFAULT 0.0,
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spend_history (
                    id SERIAL PRIMARY KEY,
                    account_id VARCHAR(50) NOT NULL,
                    date DATE NOT NULL,
                    actual_spend NUMERIC NOT NULL,
                    predicted_spend NUMERIC DEFAULT 0.0,
                    UNIQUE(account_id, date)
                );
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
    predicted_monthly_spend: float = 0.0,
    actual_monthly_spend: float = 0.0,
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
                       predicted_monthly_spend = %s,
                       actual_monthly_spend = %s,
                       analysis_result = %s,
                       status = %s
                   WHERE id = %s""",
                (
                    resources_scanned,
                    issues_found,
                    estimated_savings,
                    predicted_monthly_spend,
                    actual_monthly_spend,
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
                          estimated_savings, predicted_monthly_spend, actual_monthly_spend, status, created_at
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
                          estimated_savings, predicted_monthly_spend, actual_monthly_spend, analysis_result, status, created_at
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

# ─── Spend History operations ───

def add_spend_history(account_id: str, date_str: str, actual_spend: float, predicted_spend: float = 0.0):
    """Insert or update daily spend history."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO spend_history (account_id, date, actual_spend, predicted_spend)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (account_id, date) 
                   DO UPDATE SET actual_spend = EXCLUDED.actual_spend,
                                 predicted_spend = EXCLUDED.predicted_spend""",
                (account_id, date_str, actual_spend, predicted_spend)
            )
        conn.commit()

def get_spend_history(account_id: str, limit: int = 30) -> list[dict]:
    """Fetch spend history for plotting drift."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT date, actual_spend, predicted_spend
                   FROM spend_history
                   WHERE account_id = %s
                   ORDER BY date ASC
                   LIMIT %s""",
                (account_id, limit)
            )
            return [dict(row) for row in cur.fetchall()]

def get_dashboard_stats(user_id: int) -> dict:
    """Fetch aggregated stats for the dashboard."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Total resources scanned
            cur.execute("SELECT SUM(resources_scanned) as total_resources FROM analyses WHERE user_id = %s", (user_id,))
            res_row = cur.fetchone()
            total_resources = res_row["total_resources"] if res_row and res_row["total_resources"] else 0
            
            # Fetch all savings to parse
            cur.execute("SELECT estimated_savings FROM analyses WHERE user_id = %s", (user_id,))
            savings_rows = cur.fetchall()
            
            total_savings = 0.0
            for row in savings_rows:
                s = row["estimated_savings"]
                if s and "$" in s:
                    try:
                        # naive parse of "$100" or "$100-$200"
                        parts = s.split("$")
                        if len(parts) > 1:
                            val = parts[1].split("-")[0].strip()
                            # remove non numeric except dot
                            val = "".join(c for c in val if c.isdigit() or c == '.')
                            total_savings += float(val)
                    except:
                        pass
            
            # Fetch latest actual spend
            cur.execute("SELECT actual_spend FROM spend_history ORDER BY date DESC LIMIT 1")
            spend_row = cur.fetchone()
            current_spend = spend_row["actual_spend"] if spend_row else 0.0
            
            return {
                "total_resources": int(total_resources),
                "total_savings": total_savings,
                "current_spend": float(current_spend)
            }
