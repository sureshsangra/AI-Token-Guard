"""Tier 1: Exact Hash & Semantic Caching.
Zero token cost when a request matches a previously executed query.
"""
import hashlib
import json
import time
from typing import Optional, Dict, Any, Tuple, List
import numpy as np

class CacheEntry:
    def __init__(self, key: str, prompt_text: str, vector: np.ndarray, response_data: Dict[str, Any]):
        self.key = key
        self.prompt_text = prompt_text
        self.vector = vector
        self.response_data = response_data
        self.created_at = time.time()
        self.hits = 0

class SemanticCache:
    """Combines SHA-256 exact matching with high-speed character/word n-gram vector similarity."""
    
    def __init__(self, similarity_threshold: float = 0.92, max_entries: int = 1000):
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.exact_map: Dict[str, CacheEntry] = {}
        self.entries: List[CacheEntry] = []
        
    def _hash_messages(self, messages: List[Dict[str, Any]], model: str, temperature: float = 0.0) -> str:
        serialized = json.dumps({"messages": messages, "model": model, "temp": round(temperature, 2)}, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _extract_last_user_query(self, messages: List[Dict[str, Any]]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    return " ".join([p.get("text", "") for p in content if isinstance(p, dict)])
        return ""

    def _embed(self, text: str, dim: int = 256) -> np.ndarray:
        """Lightweight, deterministic hashing vectorizer for semantic matching without external models."""
        vec = np.zeros(dim, dtype=np.float32)
        words = text.lower().split()
        if not words:
            return vec
            
        for i, word in enumerate(words):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
            vec[h] += 1.0
            # Also capture bi-grams
            if i > 0:
                bigram = f"{words[i-1]}_{word}"
                bh = int(hashlib.md5(bigram.encode()).hexdigest(), 16) % dim
                vec[bh] += 1.5
                
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def get(self, messages: List[Dict[str, Any]], model: str, temperature: float = 0.0) -> Tuple[Optional[Dict[str, Any]], str]:
        """Check exact cache first, then semantic similarity."""
        key = self._hash_messages(messages, model, temperature)
        if key in self.exact_map:
            entry = self.exact_map[key]
            entry.hits += 1
            return entry.response_data, "exact_cache_hit"

        # If temperature is high (> 0.7), semantic cache is risky, so skip
        if temperature > 0.7:
            return None, "miss"

        query = self._extract_last_user_query(messages)
        if not query or len(query.strip()) < 8:
            return None, "miss"

        query_vec = self._embed(query)
        best_sim = 0.0
        best_entry = None

        for entry in self.entries:
            sim = float(np.dot(query_vec, entry.vector))
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        if best_sim >= self.similarity_threshold and best_entry is not None:
            best_entry.hits += 1
            return best_entry.response_data, f"semantic_cache_hit (similarity: {best_sim:.2f})"

        return None, "miss"

    def put(self, messages: List[Dict[str, Any]], model: str, temperature: float, response_data: Dict[str, Any]):
        key = self._hash_messages(messages, model, temperature)
        query = self._extract_last_user_query(messages)
        vec = self._embed(query) if query else np.zeros(256, dtype=np.float32)

        entry = CacheEntry(key=key, prompt_text=query, vector=vec, response_data=response_data)
        self.exact_map[key] = entry
        self.entries.append(entry)

        if len(self.entries) > self.max_entries:
            removed = self.entries.pop(0)
            self.exact_map.pop(removed.key, None)
