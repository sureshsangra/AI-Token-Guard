"""
Token Guard - Universal Tokenizer
==================================
Production-ready, plug-and-play token counter that works across:
  - OpenAI  (GPT-4o, GPT-4, GPT-3.5, o1, o3)
  - Google  (Gemini 2.0, 1.5 Pro/Flash)
  - Anthropic (Claude 3.5, 3 Sonnet/Haiku)
  - DeepSeek (deepseek-chat, deepseek-reasoner)

Priority order:
  1. tiktoken (exact, OpenAI-spec)  — used when installed
  2. Regex heuristic fallback       — zero extra dependencies
"""

import json
import re
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier 1 — tiktoken (exact, OpenAI-spec tokenizer)
# ---------------------------------------------------------------------------
_TIKTOKEN_AVAILABLE = False
_ENC_CACHE: Dict[str, Any] = {}

def _get_tiktoken_enc(encoding_name: str = "cl100k_base"):
    global _TIKTOKEN_AVAILABLE
    if encoding_name in _ENC_CACHE:
        return _ENC_CACHE[encoding_name]
    try:
        import tiktoken
        enc = tiktoken.get_encoding(encoding_name)
        _ENC_CACHE[encoding_name] = enc
        _TIKTOKEN_AVAILABLE = True
        return enc
    except Exception as exc:
        logger.debug("tiktoken not available (%s); using heuristic fallback.", exc)
        _ENC_CACHE[encoding_name] = None
        return None

_get_tiktoken_enc("cl100k_base")

# ---------------------------------------------------------------------------
# Tier 2 — Model-to-encoding map
# ---------------------------------------------------------------------------
_MODEL_ENCODING_MAP = {
    "gpt-4o":           "o200k_base",
    "gpt-4o-mini":      "o200k_base",
    "o1":               "o200k_base",
    "o1-mini":          "o200k_base",
    "o3":               "o200k_base",
    "o3-mini":          "o200k_base",
    "gpt-4":            "cl100k_base",
    "gpt-4-turbo":      "cl100k_base",
    "gpt-3.5-turbo":    "cl100k_base",
    "gemini-2.0-flash": "cl100k_base",
    "gemini-1.5-pro":   "cl100k_base",
    "gemini-1.5-flash": "cl100k_base",
    "claude-3-5-sonnet-20241022": "cl100k_base",
    "claude-3-5-haiku-20241022":  "cl100k_base",
    "claude-3-opus-20240229":     "cl100k_base",
    "claude-3-haiku-20240307":    "cl100k_base",
    "deepseek-chat":    "cl100k_base",
    "deepseek-reasoner":"cl100k_base",
}

def _encoding_for_model(model: str) -> str:
    model_lower = model.lower()
    if model_lower in _MODEL_ENCODING_MAP:
        return _MODEL_ENCODING_MAP[model_lower]
    for key, enc in _MODEL_ENCODING_MAP.items():
        if model_lower.startswith(key) or key in model_lower:
            return enc
    return "cl100k_base"

# ---------------------------------------------------------------------------
# Tier 3 — Heuristic regex fallback (zero dependencies)
# ---------------------------------------------------------------------------
_HEURISTIC_RE = re.compile(
    r"'s|'t|'re|'ve|'m|'ll|'d"
    r"|[a-zA-Z\u00C0-\u024F]+"
    r"|[0-9]+"
    r"|[^\s\w]+"
    r"|\s+",
    re.UNICODE,
)

def _heuristic_count(text: str) -> int:
    if not text:
        return 0
    matches = _HEURISTIC_RE.findall(text)
    if matches:
        return max(1, len(matches))
    return max(1, int(len(text) / 3.8))

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def count_text_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in a plain text string. Never raises; falls back gracefully."""
    if not text:
        return 0
    enc = _get_tiktoken_enc(_encoding_for_model(model))
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=()))
        except Exception as exc:
            logger.debug("tiktoken encode error (%s); falling back.", exc)
    return _heuristic_count(text)


def count_messages_tokens(
    messages: List[Dict[str, Any]],
    tools: Optional[Union[List[Dict[str, Any]], None]] = None,
    model: str = "gpt-4o",
) -> int:
    """
    Estimate total tokens for a full chat completion payload.
    Follows OpenAI counting formula. Compatible with OpenAI, Gemini, Claude, DeepSeek.
    """
    total = 3  # conversation priming tokens
    for msg in messages:
        total += 4  # per-message overhead
        content = msg.get("content")
        if isinstance(content, str):
            total += count_text_tokens(content, model)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total += count_text_tokens(part["text"], model)
        name = msg.get("name")
        if name:
            total += count_text_tokens(name, model) + 1
        for tc in (msg.get("tool_calls") or []):
            fn = tc.get("function", {})
            total += count_text_tokens(fn.get("name", ""), model)
            total += count_text_tokens(fn.get("arguments", ""), model)
    if tools:
        tools_str = json.dumps(tools, separators=(",", ":"), ensure_ascii=False)
        total += count_text_tokens(tools_str, model)
    return total


def tokenizer_info() -> Dict[str, Any]:
    """Return runtime info about the active tokenizer backend."""
    return {
        "backend": "tiktoken" if _TIKTOKEN_AVAILABLE else "heuristic_regex",
        "tiktoken_available": _TIKTOKEN_AVAILABLE,
        "supported_encodings": list(_ENC_CACHE.keys()),
        "supported_models": list(_MODEL_ENCODING_MAP.keys()),
        "note": (
            "Install tiktoken for exact counts: pip install tiktoken"
            if not _TIKTOKEN_AVAILABLE
            else "tiktoken active — exact token counts enabled."
        ),
    }
