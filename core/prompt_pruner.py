"""Tier 4: Prompt & Context Pruning (RTM Pruning).
Prunes low-information tokens, redundant whitespace, markdown padding, and conversational bloat.
"""
import re
from typing import List, Dict, Any, Union
import copy

class PromptPruner:
    """Intelligently compacts prompt text and removes dead tokens while preserving semantics."""

    # Common conversational boilerplate phrases that waste tokens without providing value
    BOILERPLATE_PATTERNS = [
        re.compile(r"\b(as an ai language model|as an ai assistant),?\s*", re.IGNORECASE),
        re.compile(r"\b(please note that|it is important to note that|keep in mind that)\s*", re.IGNORECASE),
        re.compile(r"\b(in order to|with the aim of)\b", re.IGNORECASE),
        re.compile(r"\b(feel free to (ask|reach out|let me know))\b", re.IGNORECASE),
        re.compile(r"\b(without further ado|needless to say)\b,?\s*", re.IGNORECASE),
    ]

    MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
    MULTIPLE_SPACES = re.compile(r"[ \t]{2,}")
    MARKDOWN_DIVIDERS = re.compile(r"(\r?\n){1,}[ \t]*[-*_]{3,}[ \t]*(\r?\n){1,}")

    def __init__(self, aggressiveness: str = "medium"):
        self.aggressiveness = aggressiveness

    def prune_text(self, text: str) -> str:
        if not text:
            return text

        # 1. Normalize line endings and collapse excessive empty lines
        text = text.replace("\r\n", "\n")
        text = self.MULTIPLE_NEWLINES.sub("\n\n", text)
        
        # 2. Collapse excessive horizontal spaces (avoiding code indentation if possible)
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            if line.startswith("    ") or line.startswith("\t"):
                # Preserve code indent
                cleaned_lines.append(line.rstrip())
            else:
                cleaned_lines.append(self.MULTIPLE_SPACES.sub(" ", line).strip())
        text = "\n".join(cleaned_lines)

        # 3. Simplify markdown horizontal rules
        text = self.MARKDOWN_DIVIDERS.sub("\n---\n", text)

        # 4. Remove conversational filler phrases in medium/aggressive mode
        if self.aggressiveness in ("medium", "aggressive"):
            for pattern in self.BOILERPLATE_PATTERNS:
                text = pattern.sub("", text)

        # 5. Remove consecutive duplicate sentences/lines often found in RAG dumps
        if self.aggressiveness == "aggressive":
            split_lines = text.split("\n")
            deduped = []
            prev = None
            for l in split_lines:
                sl = l.strip()
                if sl and sl == prev:
                    continue
                deduped.append(l)
                prev = sl
            text = "\n".join(deduped)

        return text.strip()

    def prune_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pruned_messages = []
        for msg in messages:
            clean_msg = copy.deepcopy(msg)
            content = clean_msg.get("content")
            
            if isinstance(content, str):
                clean_msg["content"] = self.prune_text(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text" and "text" in part:
                        part["text"] = self.prune_text(part["text"])
            pruned_messages.append(clean_msg)
            
        return pruned_messages
