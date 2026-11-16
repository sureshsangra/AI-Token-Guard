"""Embedded SQLite persistence for Token Guard metrics, logs, and cache.
Ensures savings history and cache survive server restarts.
"""
import sqlite3
import json
import time
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "token_guard.db")

# Approximate pricing per 1M blended tokens (input + cached)
MODEL_PRICING_PER_M = {
    "gpt-4o": 4.50,
    "gpt-4o-mini": 0.15,
    "gpt-4": 30.00,
    "o1": 15.00,
    "o3": 10.00,
    "o3-mini": 1.10,
    "claude-3-5-sonnet": 3.00,
    "claude-3-haiku": 0.25,
    "gemini-2.0-flash": 0.10,
    "gemini-1.5-flash": 0.075,
    "gemini-1.5-pro": 2.50,
    "deepseek-chat": 0.27,
    "deepseek-reasoner": 0.55,
    "grok": 3.00,
    "mistral": 2.00,
    "codestral": 1.00,
    "llama": 0.60,
    "qwen": 0.30,
}

def calculate_cost_saved(model: str, saved_tokens: int) -> float:
    price = 2.50  # Default $2.50 / 1M tokens
    m = (model or "").lower()
    for k, v in MODEL_PRICING_PER_M.items():
        if k in m:
            price = v
            break
    return round((saved_tokens / 1_000_000.0) * price, 6)

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
                    cache_status TEXT,
                    client TEXT DEFAULT 'API Client',
                    session_id TEXT DEFAULT 'Session 1',
                    cost_saved REAL DEFAULT 0.0,
                    is_simulated INTEGER DEFAULT 0,
                    date_str TEXT DEFAULT ''
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
            # Auto-migrate table columns if upgrading from earlier schema
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(request_logs)")
            existing_cols = {row[1] for row in cur.fetchall()}
            if "client" not in existing_cols:
                conn.execute("ALTER TABLE request_logs ADD COLUMN client TEXT DEFAULT 'API Client'")
            if "session_id" not in existing_cols:
                conn.execute("ALTER TABLE request_logs ADD COLUMN session_id TEXT DEFAULT 'Session 1'")
            if "cost_saved" not in existing_cols:
                conn.execute("ALTER TABLE request_logs ADD COLUMN cost_saved REAL DEFAULT 0.0")
            if "is_simulated" not in existing_cols:
                conn.execute("ALTER TABLE request_logs ADD COLUMN is_simulated INTEGER DEFAULT 0")
            if "date_str" not in existing_cols:
                conn.execute("ALTER TABLE request_logs ADD COLUMN date_str TEXT DEFAULT ''")
            conn.commit()

    def _resolve_session_id(self, client: str, date_str: str, now: float) -> str:
        """Determines the current session for this client. 
        If more than 30 minutes elapsed since last request, advances to next session.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT timestamp, session_id FROM request_logs
                WHERE client = ? AND date_str = ?
                ORDER BY id DESC LIMIT 1
            """, (client, date_str))
            row = cur.fetchone()
            if not row:
                return "Session 1"
            
            last_ts = row["timestamp"]
            last_sess = row["session_id"]
            if (now - last_ts) > 1800:  # 30 minutes inactivity
                try:
                    num = int(last_sess.replace("Session ", "").strip()) + 1
                except Exception:
                    num = 2
                return f"Session {num}"
            return last_sess

    def record_request(
        self,
        model: str,
        original: int,
        optimized: int,
        saved: int,
        savings_pct: float,
        cache_status: str,
        client: str = "API Client",
        session_id: Optional[str] = None,
        is_simulated: int = 0
    ):
        now = time.time()
        time_str = time.strftime("%H:%M:%S")
        date_str = time.strftime("%Y-%m-%d")
        cost = calculate_cost_saved(model, saved)

        if not session_id:
            session_id = self._resolve_session_id(client, date_str, now)

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO request_logs 
                (timestamp, time_str, model, original_tokens, optimized_tokens, tokens_saved, 
                 savings_percentage, cache_status, client, session_id, cost_saved, is_simulated, date_str)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, time_str, model, original, optimized, saved, savings_pct, cache_status,
                  client, session_id, cost, is_simulated, date_str))
            conn.commit()

    def get_summary(self) -> Dict[str, Any]:
        now = time.time()
        today_date = time.strftime("%Y-%m-%d")
        friendly_today = time.strftime("%b %d, %Y")

        with self._get_conn() as conn:
            cur = conn.cursor()

            # All-time summary
            cur.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    COALESCE(SUM(original_tokens), 0) as total_orig,
                    COALESCE(SUM(optimized_tokens), 0) as total_opt,
                    COALESCE(SUM(tokens_saved), 0) as total_saved,
                    COALESCE(SUM(cost_saved), 0.0) as total_cost,
                    COALESCE(SUM(CASE WHEN cache_status LIKE '%hit%' THEN 1 ELSE 0 END), 0) as hits
                FROM request_logs
            """)
            row = cur.fetchone()
            total_reqs = row["total_requests"]
            total_orig = row["total_orig"]
            total_opt = row["total_opt"]
            total_saved = row["total_saved"]
            total_cost = round(row["total_cost"], 4)
            cache_hits = row["hits"]
            overall_pct = round((total_saved / total_orig * 100.0), 2) if total_orig > 0 else 0.0

            # Today summary
            cur.execute("""
                SELECT 
                    COUNT(*) as today_requests,
                    COALESCE(SUM(original_tokens), 0) as today_orig,
                    COALESCE(SUM(optimized_tokens), 0) as today_opt,
                    COALESCE(SUM(tokens_saved), 0) as today_saved,
                    COALESCE(SUM(cost_saved), 0.0) as today_cost
                FROM request_logs
                WHERE date_str = ?
            """, (today_date,))
            t_row = cur.fetchone()
            today_orig = t_row["today_orig"]
            today_opt = t_row["today_opt"]
            today_saved = t_row["today_saved"]
            today_cost = round(t_row["today_cost"], 4)
            today_pct = round((today_saved / today_orig * 100.0), 2) if today_orig > 0 else 0.0

            # Today Sessions Breakdown (grouped by client and session_id)
            cur.execute("""
                SELECT 
                    client,
                    session_id,
                    COUNT(*) as request_count,
                    COALESCE(SUM(original_tokens), 0) as session_orig,
                    COALESCE(SUM(optimized_tokens), 0) as session_opt,
                    COALESCE(SUM(tokens_saved), 0) as session_saved,
                    COALESCE(SUM(cost_saved), 0.0) as session_cost,
                    MIN(time_str) as start_time,
                    MAX(time_str) as last_time
                FROM request_logs
                WHERE date_str = ?
                GROUP BY client, session_id
                ORDER BY MIN(timestamp) DESC
            """, (today_date,))
            sessions_list = []
            for s in cur.fetchall():
                s_orig = s["session_orig"]
                s_saved = s["session_saved"]
                s_pct = round((s_saved / s_orig * 100.0), 1) if s_orig > 0 else 0.0
                sessions_list.append({
                    "client": s["client"],
                    "session_id": s["session_id"],
                    "time_span": f"{s['start_time']} - {s['last_time']}",
                    "requests": s["request_count"],
                    "original_tokens": s_orig,
                    "optimized_tokens": s["session_opt"],
                    "tokens_saved": s_saved,
                    "savings_percentage": s_pct,
                    "cost_saved": round(s["session_cost"], 4)
                })

            # Check last seen per client (e.g. Cursor, Chrome Extension, etc.)
            cur.execute("""
                SELECT client, MAX(timestamp) as last_ts
                FROM request_logs
                GROUP BY client
            """)
            client_status = {}
            for c in cur.fetchall():
                diff = now - c["last_ts"]
                if diff < 60:
                    status_text = "🟢 Active (just now)"
                elif diff < 300:
                    status_text = f"🟢 Active ({int(diff)}s ago)"
                elif diff < 3600:
                    status_text = f"🟡 Idle ({int(diff // 60)}m ago)"
                else:
                    status_text = f"⚪ Offline ({int(diff // 3600)}h ago)"
                client_status[c["client"]] = {
                    "last_timestamp": c["last_ts"],
                    "status_text": status_text,
                    "is_active": diff < 300
                }

            # Recent 30 logs
            cur.execute("SELECT * FROM request_logs ORDER BY id DESC LIMIT 30")
            recent = [dict(r) for r in cur.fetchall()]

            # Timeline data for charts (chronological order)
            cur.execute("""
                SELECT time_str, client, original_tokens, optimized_tokens, tokens_saved, cost_saved
                FROM (SELECT * FROM request_logs ORDER BY id DESC LIMIT 20)
                ORDER BY id ASC
            """)
            chart_rows = cur.fetchall()
            timeline_chart = {
                "labels": [r["time_str"] for r in chart_rows],
                "clients": [r["client"] for r in chart_rows],
                "original": [r["original_tokens"] for r in chart_rows],
                "optimized": [r["optimized_tokens"] for r in chart_rows],
                "saved": [r["tokens_saved"] for r in chart_rows],
                "cost": [round(r["cost_saved"], 4) for r in chart_rows]
            }

            return {
                "total_requests": total_reqs,
                "total_original_tokens": total_orig,
                "total_optimized_tokens": total_opt,
                "total_tokens_saved": total_saved,
                "overall_savings_percentage": overall_pct,
                "cache_hits": cache_hits,
                "estimated_dollars_saved": total_cost,
                "today_date": friendly_today,
                "today_requests": t_row["today_requests"],
                "today_original_tokens": today_orig,
                "today_optimized_tokens": today_opt,
                "today_tokens_saved": today_saved,
                "today_savings_percentage": today_pct,
                "today_dollars_saved": today_cost,
                "sessions_today": sessions_list,
                "client_status": client_status,
                "timeline_chart": timeline_chart,
                "recent_requests": recent
            }

    def reset(self, clear_simulated_only: bool = False):
        with self._get_conn() as conn:
            if clear_simulated_only:
                conn.execute("DELETE FROM request_logs WHERE is_simulated = 1")
            else:
                conn.execute("DELETE FROM request_logs")
                conn.execute("DELETE FROM exact_cache")
            conn.commit()

store = PersistentStore()
