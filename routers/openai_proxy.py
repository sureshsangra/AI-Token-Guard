"""Multi-provider chat proxy supporting OpenAI, Google Gemini, Anthropic Claude, and DeepSeek.
Provides unified token optimization across all providers and transparent format conversion.
"""
import json
import httpx
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse

from token_guard.core.pipeline import OptimizationPipeline, OptimizationResult
from token_guard.routers.metrics import tracker
from token_guard.config import settings
from token_guard.adapters.anthropic import AnthropicAdapter

router = APIRouter(prefix="/v1", tags=["Universal AI Proxy"])
pipeline = OptimizationPipeline()

_HTTP_CLIENT = None

def get_http_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
        _HTTP_CLIENT = httpx.AsyncClient(
            timeout=120.0,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)
        )
    return _HTTP_CLIENT

def extract_api_key(client_auth_header: str, custom_key: str = None) -> str:
    if custom_key:
        return custom_key
    if not client_auth_header:
        return ""
    if client_auth_header.startswith("Bearer "):
        return client_auth_header[7:].strip()
    return client_auth_header.strip()

def detect_client(request: Request) -> str:
    ua = request.headers.get("user-agent", "").lower()
    for k, v in request.headers.items():
        k_l = k.lower()
        v_l = v.lower()
        if "antigravity" in k_l or "antigravity" in v_l or "agy" in k_l:
            return "Antigravity"
        if "cursor" in k_l or "cursor" in v_l:
            return "Cursor"
        if "continue" in k_l or "continue" in v_l:
            return "Continue.dev"
        if "cline" in k_l or "cline" in v_l or "roo" in k_l:
            return "Cline"
    if "antigravity" in ua or "agy" in ua:
        return "Antigravity"
    if "cursor" in ua:
        return "Cursor"
    if "code" in ua or "vscode" in ua:
        return "VS Code"
    if "python" in ua or "httpx" in ua or "requests" in ua:
        return "Python SDK"
    if "node" in ua or "axios" in ua or "undici" in ua:
        return "Node.js SDK"
    if "chrome" in ua or "mozilla" in ua or "safari" in ua:
        return "Web Browser"
    # Official TypeScript SDK headers commonly used by Cursor & VS Code extensions
    if request.headers.get("x-stainless-os") or request.headers.get("x-stainless-lang"):
        return "Cursor"
    return "API Client"

@router.post("/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    client_name = detect_client(request)
    client_auth = request.headers.get("Authorization", "")
    model = body.get("model", "gpt-4o")
    stream = body.get("stream", False)
    temperature = float(body.get("temperature", 0.0))

    # Run the 4-tier optimization pipeline with Safe Failover
    try:
        opt_result: OptimizationResult = pipeline.optimize_request(body)
    except Exception as e:
        # Never fail upstream calls if formatting has unforeseen edge-cases
        opt_result = OptimizationResult(
            is_cached=False,
            cache_type="bypass_error",
            cached_response=None,
            original_tokens=0,
            optimized_tokens=0,
            tokens_saved=0,
            savings_percentage=0.0,
            optimized_messages=body.get("messages", []),
            optimized_tools=body.get("tools")
        )

    # 1. Handle Cache Hit (100% token savings)
    if opt_result.is_cached and opt_result.cached_response:
        tracker.record(
            model=model,
            original=opt_result.original_tokens,
            optimized=0,
            saved=opt_result.tokens_saved,
            savings_pct=100.0,
            cache_status=opt_result.cache_type,
            client=client_name
        )
        resp_data = opt_result.cached_response
        headers = {
            "X-TokenGuard-Savings": "100%",
            "X-TokenGuard-Saved-Tokens": str(opt_result.tokens_saved),
            "X-TokenGuard-Status": opt_result.cache_type,
            "X-TokenGuard-Client": client_name
        }
        return Response(content=json.dumps(resp_data), media_type="application/json", headers=headers)

    # 2. Build optimized payload
    optimized_payload = dict(body)
    optimized_payload["messages"] = opt_result.optimized_messages
    if opt_result.optimized_tools is not None:
        optimized_payload["tools"] = opt_result.optimized_tools

    # Record metrics for cache miss
    tracker.record(
        model=model,
        original=opt_result.original_tokens,
        optimized=opt_result.optimized_tokens,
        saved=opt_result.tokens_saved,
        savings_pct=opt_result.savings_percentage,
        cache_status=opt_result.cache_type,
        client=client_name
    )

    savings_headers = {
        "X-TokenGuard-Savings": f"{opt_result.savings_percentage}%",
        "X-TokenGuard-Original-Tokens": str(opt_result.original_tokens),
        "X-TokenGuard-Optimized-Tokens": str(opt_result.optimized_tokens),
        "X-TokenGuard-Saved-Tokens": str(opt_result.tokens_saved),
        "X-TokenGuard-Status": "optimized",
        "X-TokenGuard-Client": client_name
    }

    client = get_http_client()

    # --- UNIVERSAL ROUTING LOGIC ---

    # 1. ANTHROPIC CLAUDE ROUTING & ADAPTATION
    if "claude" in model.lower() or (client_auth and "sk-ant-" in client_auth):
        anthropic_body, anthropic_headers = AnthropicAdapter.openai_to_anthropic_payload(optimized_payload)
        api_key = extract_api_key(client_auth, settings.ANTHROPIC_API_KEY)
        anthropic_headers["x-api-key"] = api_key
        upstream_url = f"{settings.CLAUDE_BASE_URL}/messages"

        if stream:
            async def stream_claude():
                async with client.stream("POST", upstream_url, json=anthropic_body, headers=anthropic_headers) as upstream_resp:
                    if upstream_resp.status_code != 200:
                        err_body = await upstream_resp.aread()
                        yield f"data: {json.dumps({'error': err_body.decode()})}\n\n".encode("utf-8")
                        return
                    async for chunk in AnthropicAdapter.translate_anthropic_stream(upstream_resp, model):
                        yield chunk

            return StreamingResponse(stream_claude(), media_type="text/event-stream", headers=savings_headers)
        else:
            try:
                upstream_resp = await client.post(upstream_url, json=anthropic_body, headers=anthropic_headers)
                if upstream_resp.status_code != 200:
                    return Response(content=upstream_resp.content, status_code=upstream_resp.status_code, media_type="application/json")
                
                raw_json = upstream_resp.json()
                openai_formatted = AnthropicAdapter.anthropic_to_openai_response(raw_json, model)
                
                # Store in cache
                pipeline.record_response(
                    messages=body.get("messages", []),
                    model=model,
                    temperature=temperature,
                    response_data=openai_formatted
                )
                return Response(content=json.dumps(openai_formatted), status_code=200, media_type="application/json", headers=savings_headers)
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Claude upstream error: {str(e)}")

    # 2. XAI / GROK ROUTING (Supports grok-2, grok-beta, grok-4.7, etc.)
    elif "grok" in model.lower() or (client_auth and "xai-" in client_auth):
        api_key = extract_api_key(client_auth, settings.XAI_API_KEY)
        upstream_url = f"{settings.XAI_BASE_URL}/chat/completions"
        upstream_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    # 3. GOOGLE GEMINI ROUTING
    elif "gemini" in model.lower() or (client_auth and "AIza" in client_auth):
        api_key = extract_api_key(client_auth, settings.GEMINI_API_KEY)
        upstream_url = f"{settings.GEMINI_BASE_URL}/chat/completions"
        upstream_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "x-goog-api-key": api_key
        }

    # 4. DEEPSEEK ROUTING
    elif "deepseek" in model.lower():
        api_key = extract_api_key(client_auth, settings.DEEPSEEK_API_KEY)
        upstream_url = f"{settings.DEEPSEEK_BASE_URL}/chat/completions"
        upstream_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    # 5. MISTRAL AI / CODESTRAL ROUTING
    elif "mistral" in model.lower() or "codestral" in model.lower() or "pixtral" in model.lower():
        api_key = extract_api_key(client_auth, settings.MISTRAL_API_KEY)
        upstream_url = f"{settings.MISTRAL_BASE_URL}/chat/completions"
        upstream_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    # 6. GROQ ULTRA-FAST ROUTING
    elif "groq" in model.lower() or (client_auth and "gsk_" in client_auth):
        api_key = extract_api_key(client_auth, settings.GROQ_API_KEY)
        upstream_url = f"{settings.GROQ_BASE_URL}/chat/completions"
        upstream_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    # 7. OPENROUTER ROUTING (Universal Fallback for 200+ models)
    elif "openrouter" in model.lower() or (client_auth and "sk-or-" in client_auth) or "/" in model:
        api_key = extract_api_key(client_auth, settings.OPENROUTER_API_KEY)
        upstream_url = f"{settings.OPENROUTER_BASE_URL}/chat/completions"
        upstream_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    # 8. OLLAMA / LOCAL LLM ROUTING
    elif "ollama" in model.lower() or "localhost" in model.lower():
        upstream_url = f"{settings.OLLAMA_BASE_URL}/chat/completions"
        upstream_headers = {
            "Content-Type": "application/json"
        }

    # 9. DEFAULT OPENAI (AND UNIVERSAL OPENAI-COMPATIBLE FALLBACK)
    else:
        api_key = extract_api_key(client_auth, settings.OPENAI_API_KEY)
        upstream_url = f"{settings.OPENAI_BASE_URL}/chat/completions"
        upstream_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    # Standard OpenAI-format forwarder (used by OpenAI, Grok, Gemini, DeepSeek, etc.)
    if stream:
        async def stream_generator():
            async with client.stream("POST", upstream_url, json=optimized_payload, headers=upstream_headers) as upstream_resp:
                if upstream_resp.status_code != 200:
                    err_bytes = await upstream_resp.aread()
                    err_str = err_bytes.decode("utf-8", errors="ignore")
                    # Send friendly SSE error chunk so Cursor displays the explanation in chat
                    err_msg = (
                        f"\n\n⚠️ **[Token Guard — Upstream Error {upstream_resp.status_code}]**\n\n"
                        f"The model provider rejected the request:\n```\n{err_str}\n```\n\n"
                        f"**Troubleshooting:**\n"
                        f"- You selected model: `{model}`\n"
                        f"- Upstream URL: `{upstream_url}`\n"
                        f"- If using **Grok**, ensure you configured an xAI API key (`xai-...`) in Cursor or `.env`.\n"
                        f"- If using an **OpenAI key** (`sk-...`), switch model in Cursor to **`gpt-4o`** or **`gpt-4o-mini`**."
                    )
                    error_chunk = {
                        "id": "tg-err",
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": err_msg},
                            "finish_reason": "stop"
                        }]
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"
                    return

                async for chunk in upstream_resp.aiter_bytes():
                    yield chunk

        return StreamingResponse(stream_generator(), media_type="text/event-stream", headers=savings_headers)
    else:
        try:
            upstream_resp = await client.post(upstream_url, json=optimized_payload, headers=upstream_headers)
            
            if upstream_resp.status_code == 200:
                resp_json = upstream_resp.json()
                pipeline.record_response(
                    messages=body.get("messages", []),
                    model=model,
                    temperature=temperature,
                    response_data=resp_json
                )

            return Response(
                content=upstream_resp.content,
                status_code=upstream_resp.status_code,
                media_type="application/json",
                headers=savings_headers
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Upstream provider connection error: {str(e)}")


@router.post("/messages")
async def native_anthropic_messages(request: Request):
    """Direct Anthropic Messages API support for native Anthropic clients."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    client_api_key = request.headers.get("x-api-key") or extract_api_key(request.headers.get("Authorization", ""), settings.ANTHROPIC_API_KEY)
    model = body.get("model", "claude-3-5-sonnet-20241022")
    stream = body.get("stream", False)

    # Convert to standard format to run through pipeline
    system_prompt = body.get("system", "")
    conv_messages = []
    if system_prompt:
        conv_messages.append({"role": "system", "content": system_prompt})
    conv_messages.extend(body.get("messages", []))

    pipeline_payload = {
        "model": model,
        "messages": conv_messages,
        "temperature": body.get("temperature", 0.7),
        "tools": body.get("tools")
    }

    opt_result = pipeline.optimize_request(pipeline_payload)

    # Separate system messages back out
    opt_sys = []
    opt_msgs = []
    for m in opt_result.optimized_messages:
        if m.get("role") == "system":
            opt_sys.append(m.get("content", ""))
        else:
            opt_msgs.append(m)

    optimized_anthropic_body = dict(body)
    optimized_anthropic_body["messages"] = opt_msgs
    if opt_sys:
        optimized_anthropic_body["system"] = "\n\n".join(opt_sys)

    savings_headers = {
        "X-TokenGuard-Savings": f"{opt_result.savings_percentage}%",
        "X-TokenGuard-Original-Tokens": str(opt_result.original_tokens),
        "X-TokenGuard-Optimized-Tokens": str(opt_result.optimized_tokens),
        "X-TokenGuard-Saved-Tokens": str(opt_result.tokens_saved)
    }

    client = httpx.AsyncClient(timeout=120.0)
    upstream_url = f"{settings.CLAUDE_BASE_URL}/messages"
    upstream_headers = {
        "Content-Type": "application/json",
        "x-api-key": client_api_key,
        "anthropic-version": "2023-06-01"
    }

    if stream:
        async def stream_raw():
            try:
                async with client.stream("POST", upstream_url, json=optimized_anthropic_body, headers=upstream_headers) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
            finally:
                await client.aclose()

        return StreamingResponse(stream_raw(), media_type="text/event-stream", headers=savings_headers)
    else:
        try:
            resp = await client.post(upstream_url, json=optimized_anthropic_body, headers=upstream_headers)
            await client.aclose()
            return Response(content=resp.content, status_code=resp.status_code, media_type="application/json", headers=savings_headers)
        except Exception as e:
            await client.aclose()
            raise HTTPException(status_code=502, detail=f"Anthropic upstream error: {str(e)}")


@router.get("/models")
async def list_models():
    """Returns a list of supported models across OpenAI, Grok, Gemini, Claude, DeepSeek, and Mistral."""
    return {
        "object": "list",
        "data": [
            # OpenAI
            {"id": "gpt-4o", "object": "model", "owned_by": "openai"},
            {"id": "gpt-4o-mini", "object": "model", "owned_by": "openai"},
            {"id": "o1", "object": "model", "owned_by": "openai"},
            {"id": "o3-mini", "object": "model", "owned_by": "openai"},
            {"id": "gpt-4", "object": "model", "owned_by": "openai"},
            {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "openai"},
            # xAI / Grok
            {"id": "grok-beta", "object": "model", "owned_by": "xai"},
            {"id": "grok-2", "object": "model", "owned_by": "xai"},
            {"id": "grok-2-latest", "object": "model", "owned_by": "xai"},
            {"id": "grok-2-vision-latest", "object": "model", "owned_by": "xai"},
            {"id": "grok-4.7", "object": "model", "owned_by": "xai"},
            # Google Gemini
            {"id": "gemini-2.0-flash", "object": "model", "owned_by": "google"},
            {"id": "gemini-1.5-pro", "object": "model", "owned_by": "google"},
            {"id": "gemini-1.5-flash", "object": "model", "owned_by": "google"},
            # Anthropic Claude
            {"id": "claude-3-5-sonnet-20241022", "object": "model", "owned_by": "anthropic"},
            {"id": "claude-3-5-haiku-20241022", "object": "model", "owned_by": "anthropic"},
            {"id": "claude-3-haiku-20240307", "object": "model", "owned_by": "anthropic"},
            # DeepSeek
            {"id": "deepseek-chat", "object": "model", "owned_by": "deepseek"},
            {"id": "deepseek-reasoner", "object": "model", "owned_by": "deepseek"},
            # Mistral
            {"id": "mistral-large-latest", "object": "model", "owned_by": "mistral"},
            {"id": "codestral-latest", "object": "model", "owned_by": "mistral"},
            # Groq & Open Source
            {"id": "llama-3.3-70b-versatile", "object": "model", "owned_by": "groq"},
            {"id": "llama-3.1-8b-instant", "object": "model", "owned_by": "groq"}
        ]
    }
