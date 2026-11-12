"""Anthropic format translator.
Translates OpenAI Chat Completion requests & responses to/from Anthropic Messages API.
Allows Cursor, VS Code, and OpenAI SDKs to transparently use Claude models with full token savings.
"""
import json
import time
from typing import Dict, Any, Tuple, AsyncGenerator

class AnthropicAdapter:
    @staticmethod
    def openai_to_anthropic_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Converts OpenAI chat completions body to Anthropic Messages API format."""
        model = payload.get("model", "claude-3-5-sonnet-20241022")
        messages = payload.get("messages", [])
        temperature = payload.get("temperature", 0.7)
        max_tokens = payload.get("max_tokens") or payload.get("max_completion_tokens") or 4096
        stream = payload.get("stream", False)

        system_prompts = []
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "system":
                if isinstance(content, str):
                    system_prompts.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and "text" in part:
                            system_prompts.append(part["text"])
            elif role in ("user", "assistant"):
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })

        anthropic_body: Dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": min(1.0, max(0.0, float(temperature))),
            "stream": stream
        }

        if system_prompts:
            anthropic_body["system"] = "\n\n".join(system_prompts)

        # Handle tools if present
        tools = payload.get("tools")
        if tools:
            anthropic_tools = []
            for t in tools:
                if t.get("type") == "function" and "function" in t:
                    fn = t["function"]
                    anthropic_tools.append({
                        "name": fn.get("name", ""),
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {"type": "object", "properties": {}})
                    })
            if anthropic_tools:
                anthropic_body["tools"] = anthropic_tools

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        return anthropic_body, headers

    @staticmethod
    def anthropic_to_openai_response(anthropic_resp: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Translates Anthropic JSON response to OpenAI Chat Completion format."""
        text_content = ""
        tool_calls = []

        for block in anthropic_resp.get("content", []):
            if block.get("type") == "text":
                text_content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id", "call_1"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input", {}))
                    }
                })

        finish_reason = "stop"
        stop_reason = anthropic_resp.get("stop_reason")
        if stop_reason == "max_tokens":
            finish_reason = "length"
        elif stop_reason == "tool_use":
            finish_reason = "tool_calls"

        usage = anthropic_resp.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        message: Dict[str, Any] = {
            "role": "assistant",
            "content": text_content if text_content or not tool_calls else None
        }
        if tool_calls:
            message["tool_calls"] = tool_calls

        return {
            "id": f"chatcmpl-{anthropic_resp.get('id', 'msg_default')}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": finish_reason
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }

    @staticmethod
    async def translate_anthropic_stream(upstream_stream, model: str) -> AsyncGenerator[bytes, None]:
        """Converts Anthropic SSE event stream into standard OpenAI SSE chunks."""
        msg_id = f"chatcmpl-{int(time.time())}"
        
        async for line in upstream_stream.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            
            raw_data = line[6:].strip()
            if raw_data == "[DONE]":
                yield b"data: [DONE]\n\n"
                continue

            try:
                event_data = json.loads(raw_data)
            except Exception:
                continue

            event_type = event_data.get("type")

            if event_type == "content_block_delta":
                delta = event_data.get("delta", {})
                if delta.get("type") == "text_delta":
                    chunk_text = delta.get("text", "")
                    openai_chunk = {
                        "id": msg_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": chunk_text},
                                "finish_reason": None
                            }
                        ]
                    }
                    yield f"data: {json.dumps(openai_chunk)}\n\n".encode("utf-8")

            elif event_type == "message_stop":
                openai_chunk = {
                    "id": msg_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }
                    ]
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
