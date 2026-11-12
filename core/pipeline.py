"""Core Optimization Pipeline orchestrating all 4 tiers."""
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel

from token_guard.tokenizer import count_messages_tokens
from token_guard.core.cache import SemanticCache
from token_guard.core.schema_minifier import SchemaMinifier
from token_guard.core.history_condenser import HistoryCondenser
from token_guard.core.prompt_pruner import PromptPruner
from token_guard.config import settings

class OptimizationResult(BaseModel):
    is_cached: bool = False
    cache_type: str = "miss"
    cached_response: Optional[Dict[str, Any]] = None
    
    original_tokens: int = 0
    optimized_tokens: int = 0
    tokens_saved: int = 0
    savings_percentage: float = 0.0
    
    optimized_messages: List[Dict[str, Any]] = []
    optimized_tools: Optional[List[Dict[str, Any]]] = None

class OptimizationPipeline:
    def __init__(self):
        self.cache = SemanticCache(similarity_threshold=settings.SEMANTIC_CACHE_THRESHOLD)
        self.schema_minifier = SchemaMinifier()
        self.history_condenser = HistoryCondenser(max_recent_turns=settings.MAX_HISTORY_TURNS)
        self.prompt_pruner = PromptPruner(aggressiveness=settings.PRUNER_AGGRESSIVENESS)

    def optimize_request(self, payload: Dict[str, Any]) -> OptimizationResult:
        messages = payload.get("messages", [])
        tools = payload.get("tools")
        model = payload.get("model", "unknown")
        temperature = float(payload.get("temperature", 0.0))

        # Calculate original baseline tokens
        orig_tokens = count_messages_tokens(messages, tools)

        # Tier 1: Check Exact & Semantic Cache
        if settings.ENABLE_EXACT_CACHE or settings.ENABLE_SEMANTIC_CACHE:
            cached_resp, cache_status = self.cache.get(messages, model, temperature)
            if cached_resp is not None:
                return OptimizationResult(
                    is_cached=True,
                    cache_type=cache_status,
                    cached_response=cached_resp,
                    original_tokens=orig_tokens,
                    optimized_tokens=0,
                    tokens_saved=orig_tokens,
                    savings_percentage=100.0,
                    optimized_messages=messages,
                    optimized_tools=tools
                )

        optimized_messages = messages
        optimized_tools = tools

        # Tier 2: Tool Schema Minifier
        if settings.ENABLE_SCHEMA_MINIFIER and optimized_tools:
            optimized_tools = self.schema_minifier.minify_tools(optimized_tools)

        # Tier 3: Conversation History Condenser
        if settings.ENABLE_HISTORY_CONDENSER and optimized_messages:
            optimized_messages = self.history_condenser.condense(optimized_messages)

        # Tier 4: Prompt & Context Pruner
        if settings.ENABLE_PROMPT_PRUNER and optimized_messages:
            optimized_messages = self.prompt_pruner.prune_messages(optimized_messages)

        # Calculate optimized tokens
        opt_tokens = count_messages_tokens(optimized_messages, optimized_tools)
        tokens_saved = max(0, orig_tokens - opt_tokens)
        savings_pct = round((tokens_saved / orig_tokens * 100.0), 2) if orig_tokens > 0 else 0.0

        return OptimizationResult(
            is_cached=False,
            cache_type="miss",
            cached_response=None,
            original_tokens=orig_tokens,
            optimized_tokens=opt_tokens,
            tokens_saved=tokens_saved,
            savings_percentage=savings_pct,
            optimized_messages=optimized_messages,
            optimized_tools=optimized_tools
        )

    def record_response(self, messages: List[Dict[str, Any]], model: str, temperature: float, response_data: Dict[str, Any]):
        """Store response in cache for subsequent matching."""
        if settings.ENABLE_EXACT_CACHE or settings.ENABLE_SEMANTIC_CACHE:
            self.cache.put(messages, model, temperature, response_data)
