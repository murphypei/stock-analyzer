"""SQLite-backed cache for API responses."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from src.config import Config


class SQLiteCache:
    """Simple key-value cache with TTL."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Config.ensure_cache_dir() / "cache.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_created
                ON cache(created_at)
                """
            )

    def _make_key(self, *parts: str) -> str:
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, source: str, stock_code: str, data_type: str, period: str = "") -> Any:
        key = self._make_key(source, stock_code, data_type, period)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value, created_at FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            value, created_at = row
            # Simple TTL check: if older than N days, treat as miss
            import datetime

            created = datetime.datetime.fromisoformat(created_at)
            if (datetime.datetime.now() - created).days > Config.CACHE_TTL_DAYS:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None
            return json.loads(value)

    def set(self, source: str, stock_code: str, data_type: str, period: str, value: Any) -> None:
        key = self._make_key(source, stock_code, data_type, period)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cache (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    created_at = CURRENT_TIMESTAMP
                """,
                (key, json.dumps(value, default=str)),
            )
