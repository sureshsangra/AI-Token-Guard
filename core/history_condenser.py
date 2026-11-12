"""Tier 3: Conversation History Summarizer & Sliding Window.
Prevents context window bloat in multi-turn dialogues while keeping system instructions intact.
"""
from typing import List, Dict, Any
import copy

class HistoryCondenser:
    """Condenses old multi-turn messages into concise context summaries while preserving system instructions."""

    def __init__(self, max_recent_turns: int = 6):
        self.max_recent_turns = max_recent_turns

    def condense(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(messages) <= self.max_recent_turns + 2:
            return messages

        system_messages = []
        non_system = []

        for msg in messages:
            if msg.get("role") == "system":
                system_messages.append(msg)
            else:
                non_system.append(msg)

        if len(non_system) <= self.max_recent_turns:
            return messages

        # Split into older messages to condense and recent messages to preserve
        cutoff = len(non_system) - self.max_recent_turns
        older_messages = non_system[:cutoff]
        recent_messages = non_system[cutoff:]

        # Create high-density condensed summary of older messages
        condensed_bullets = []
        for msg in older_messages:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            
            if isinstance(content, list):
                # Extract text parts
                content = " ".join([p.get("text", "") for p in content if isinstance(p, dict)])
            
            # Extract first ~120 characters or key takeaway
            clean_text = " ".join(str(content).split())
            if len(clean_text) > 140:
                clean_text = clean_text[:137] + "..."
                
            if clean_text:
                condensed_bullets.append(f"- {role}: {clean_text}")

        summary_content = (
            "[Compressed Prior Context]\n" + "\n".join(condensed_bullets)
        )

        condensed_summary_msg = {
            "role": "system",
            "content": summary_content
        }

        candidate = system_messages + [condensed_summary_msg] + recent_messages

        # Only apply if the candidate representation is strictly more compact than original
        from token_guard.tokenizer import count_messages_tokens
        if count_messages_tokens(candidate) < count_messages_tokens(messages):
            return candidate
            
        return messages
