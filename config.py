"""Configuration settings for Token Guard Proxy."""
import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    HOST: str = os.getenv("TOKEN_GUARD_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("TOKEN_GUARD_PORT", "8088"))
    
    # Upstream Endpoints
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    GEMINI_BASE_URL: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
    CLAUDE_BASE_URL: str = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1")
    
    # API Keys (optional if passed by client in Authorization header)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    
    # Optimization Engine Flags
    ENABLE_EXACT_CACHE: bool = os.getenv("ENABLE_EXACT_CACHE", "true").lower() == "true"
    ENABLE_SEMANTIC_CACHE: bool = os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() == "true"
    SEMANTIC_CACHE_THRESHOLD: float = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.85"))
    
    ENABLE_SCHEMA_MINIFIER: bool = os.getenv("ENABLE_SCHEMA_MINIFIER", "true").lower() == "true"
    
    ENABLE_HISTORY_CONDENSER: bool = os.getenv("ENABLE_HISTORY_CONDENSER", "true").lower() == "true"
    MAX_HISTORY_TURNS: int = int(os.getenv("MAX_HISTORY_TURNS", "6"))
    
    ENABLE_PROMPT_PRUNER: bool = os.getenv("ENABLE_PROMPT_PRUNER", "true").lower() == "true"
    PRUNER_AGGRESSIVENESS: str = os.getenv("PRUNER_AGGRESSIVENESS", "medium") # "light", "medium", "aggressive"

settings = Settings()
