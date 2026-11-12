"""Metrics and Live Statistics for Token Guard Proxy."""
import time
from typing import List, Dict, Any
from fastapi import APIRouter
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
    def record(self, model: str, original: int, optimized: int, saved: int, savings_pct: float, cache_status: str):
        store.record_request(
            model=model,
            original=original,
            optimized=optimized,
            saved=saved,
            savings_pct=savings_pct,
            cache_status=cache_status
        )

    def get_summary(self) -> Dict[str, Any]:
        return store.get_summary()

    def reset(self):
        store.reset()

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
        cache_status=event.cache_status
    )
    return {"status": "ok", "total_saved": store.get_summary()["total_tokens_saved"]}

@router.post("/api/simulate")
@router.post("/simulate")
async def simulate_sample_request():
    """Generates a sample request to test and showcase dashboard metrics immediately."""
    import random
    models = ["gpt-4o", "gemini-2.0-flash", "claude-3-5-sonnet", "ChatGPT Web"]
    chosen_model = random.choice(models)
    orig = random.randint(450, 1800)
    saved = int(orig * random.uniform(0.28, 0.58))
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
        cache_status=status
    )
    return tracker.get_summary()

@router.get("/metrics")
async def get_metrics():
    """Return live token reduction statistics and history."""
    return tracker.get_summary()

@router.post("/metrics/reset")
async def reset_metrics():
    global tracker
    tracker = MetricsTracker()
    return {"status": "reset_success"}
