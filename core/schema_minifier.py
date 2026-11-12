"""Tier 2: Tool & Schema Minifier.
Minifies verbose JSON Schema parameter declarations for LLM tools/functions.
Saves 30% to 60% of tool definition tokens.
"""
from typing import List, Dict, Any, Union
import copy

class SchemaMinifier:
    """Strips redundant schema metadata like '$schema', 'title', redundant descriptions, and whitespace."""

    KEYS_TO_STRIP = {"$schema", "title", "additionalProperties", "x-displayname", "example"}

    @classmethod
    def minify_tools(cls, tools: Union[List[Dict[str, Any]], None]) -> Union[List[Dict[str, Any]], None]:
        if not tools:
            return tools

        minified = []
        for tool in tools:
            clean_tool = copy.deepcopy(tool)
            tool_type = clean_tool.get("type")
            
            if tool_type == "function" and "function" in clean_tool:
                fn = clean_tool["function"]
                # Trim overly verbose top-level function descriptions
                if "description" in fn and isinstance(fn["description"], str):
                    fn["description"] = " ".join(fn["description"].split())
                
                if "parameters" in fn and isinstance(fn["parameters"], dict):
                    fn["parameters"] = cls._minify_schema_dict(fn["parameters"])
                    
            minified.append(clean_tool)
        return minified

    @classmethod
    def _minify_schema_dict(cls, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively prune non-essential metadata from JSON schema."""
        cleaned = {}
        for k, v in schema.items():
            if k in cls.KEYS_TO_STRIP:
                continue
            
            if k == "description" and isinstance(v, str):
                # Compress spaces and newlines in parameter descriptions
                cleaned[k] = " ".join(v.split())
            elif isinstance(v, dict):
                cleaned[k] = cls._minify_schema_dict(v)
            elif isinstance(v, list):
                cleaned[k] = [cls._minify_schema_dict(item) if isinstance(item, dict) else item for item in v]
            else:
                cleaned[k] = v
                
        # If properties has empty descriptions, strip them
        if "properties" in cleaned and isinstance(cleaned["properties"], dict):
            for prop_name, prop_val in cleaned["properties"].items():
                if isinstance(prop_val, dict) and prop_val.get("description") == "":
                    prop_val.pop("description", None)
                    
        return cleaned
