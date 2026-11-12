"""Embedded SQLite persistence for Token Guard metrics, logs, and cache.
Ensures savings history and cache survive server restarts.
"""
import sqlite3
import json
import time
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "token_guard.db")

class PersistentStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    time_str TEXT,
                    model TEXT,
                    original_tokens INTEGER,
                    optimized_tokens INTEGER,
                    tokens_saved INTEGER,
                    savings_percentage REAL,
                    cache_status TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exact_cache (
                    key TEXT PRIMARY KEY,
                    model TEXT,
                    response_json TEXT,
                    created_at REAL,
                    hits INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def record_request(self, model: str, original: int, optimized: int, saved: int, savings_pct: float, cache_status: str):
        now = time.time()
        time_str = time.strftime("%H:%M:%S")
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO request_logs 
                (timestamp, time_str, model, original_tokens, optimized_tokens, tokens_saved, savings_percentage, cache_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, time_str, model, original, optimized, saved, savings_pct, cache_status))
            conn.commit()

    def get_summary(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    COALESCE(SUM(original_tokens), 0) as total_orig,
                    COALESCE(SUM(optimized_tokens), 0) as total_opt,
                    COALESCE(SUM(tokens_saved), 0) as total_saved,
                    COALESCE(SUM(CASE WHEN cache_status LIKE '%hit%' THEN 1 ELSE 0 END), 0) as hits
                FROM request_logs
            """)
            row = cur.fetchone()
            
            total_reqs = row["total_requests"]
            total_orig = row["total_orig"]
            total_opt = row["total_opt"]
            total_saved = row["total_saved"]
            cache_hits = row["hits"]
            
            overall_pct = round((total_saved / total_orig * 100.0), 2) if total_orig > 0 else 0.0
            est_dollars = round((total_saved / 1_000_000.0) * 2.50, 4)

            # Recent 25 logs
            cur.execute("SELECT * FROM request_logs ORDER BY id DESC LIMIT 25")
            recent = [dict(r) for r in cur.fetchall()]

            return {
                "total_requests": total_reqs,
                "total_original_tokens": total_orig,
                "total_optimized_tokens": total_opt,
                "total_tokens_saved": total_saved,
                "overall_savings_percentage": overall_pct,
                "cache_hits": cache_hits,
                "estimated_dollars_saved": est_dollars,
                "recent_requests": recent
            }

    def reset(self):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM request_logs")
            conn.execute("DELETE FROM exact_cache")
            conn.commit()

store = PersistentStore()
