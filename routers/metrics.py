"""Metrics and Live Statistics for Token Guard Proxy."""
import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(tags=["Metrics"])

class RequestLog(BaseModel):
    timestamp: float
    model: str
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    savings_percentage: float
    cache_status: str

from token_guard.core.storage import store

class MetricsTracker:
    def record(
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
        store.record_request(
            model=model,
            original=original,
            optimized=optimized,
            saved=saved,
            savings_pct=savings_pct,
            cache_status=cache_status,
            client=client,
            session_id=session_id,
            is_simulated=is_simulated
        )

    def get_summary(self) -> Dict[str, Any]:
        return store.get_summary()

    def reset(self, clear_simulated_only: bool = False):
        store.reset(clear_simulated_only=clear_simulated_only)

tracker = MetricsTracker()

class ExtensionEvent(BaseModel):
    source: str
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    savings_percentage: float
    cache_status: str = "browser_prune"

@router.post("/api/extension/log")
@router.post("/extension/log")
async def log_extension_event(event: ExtensionEvent):
    """Receive and record token savings directly from the Chrome extension."""
    tracker.record(
        model=event.source,
        original=event.original_tokens,
        optimized=event.optimized_tokens,
        saved=event.tokens_saved,
        savings_pct=event.savings_percentage,
        cache_status=event.cache_status,
        client=f"Chrome Extension ({event.source})",
        is_simulated=0
    )
    return {"status": "ok", "total_saved": store.get_summary()["total_tokens_saved"]}

@router.post("/api/simulate")
@router.post("/simulate")
async def simulate_sample_request():
    """Generates a sample request to test and showcase dashboard metrics immediately."""
    import random
    models = ["gpt-4o", "gemini-2.0-flash", "claude-3-5-sonnet"]
    chosen_model = random.choice(models)
    orig = random.randint(600, 2200)
    saved = int(orig * random.uniform(0.35, 0.62))
    opt = orig - saved
    pct = round((saved / orig) * 100, 1)
    status = random.choice(["optimized", "exact_cache_hit", "optimized", "semantic_cache_hit"])
    if "hit" in status:
        opt = 0
        saved = orig
        pct = 100.0

    tracker.record(
        model=chosen_model,
        original=orig,
        optimized=opt,
        saved=saved,
        savings_pct=pct,
        cache_status=status,
        client="Cursor",
        is_simulated=1
    )
    return tracker.get_summary()

@router.get("/metrics")
async def get_metrics():
    """Return live token reduction statistics, sessions breakdown, and chart data."""
    return tracker.get_summary()

@router.post("/metrics/reset")
async def reset_metrics(simulated_only: bool = False):
    """Resets metrics database. If simulated_only=True, only clears mock data."""
    tracker.reset(clear_simulated_only=simulated_only)
    return {"status": "reset_success", "cleared_simulated_only": simulated_only}
