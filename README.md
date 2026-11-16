<div align="center">

# 🛡️ Token Guard

**Universal Plug-and-Play Token Optimization Proxy**

Cut your LLM costs by **30 – 70 %** across OpenAI, Google Gemini, Anthropic Claude, and DeepSeek with a single `base_url` change.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker)](Dockerfile)
[![GitHub Stars](https://img.shields.io/github/stars/sureshsangra/AI-Token-Guard?style=social)](https://github.com/sureshsangra/AI-Token-Guard)
[![GitHub Forks](https://img.shields.io/github/forks/sureshsangra/AI-Token-Guard?style=social)](https://github.com/sureshsangra/AI-Token-Guard/fork)

</div>

---

## What is Token Guard?

Token Guard is a **local reverse proxy** that sits between your application and any LLM provider.
It intercepts your API calls, runs them through a 4-tier token compression pipeline, then forwards the leaner payload upstream — all transparently, in under 2 ms.

```
Your App / IDE
      │
      │  base_url = http://localhost:8088/v1
      ▼
┌─────────────────────────────────────┐
│          TOKEN GUARD PROXY          │
│                                     │
│  Tier 1 → Exact + Semantic Cache   │  ← 100 % savings on cache hit
│  Tier 2 → Tool/Schema Minifier     │  ← 30–60 % off tool definitions
│  Tier 3 → History Condenser        │  ← 20–50 % off long dialogues
│  Tier 4 → Prompt Pruner            │  ← 15–55 % off verbose text
└─────────────────────────────────────┘
      │
      ├──▶  OpenAI API
      ├──▶  Google Gemini API
      ├──▶  Anthropic Claude API
      ├──▶  xAI Grok API
      ├──▶  DeepSeek API
      ├──▶  Mistral AI & Codestral API
      └──▶  Groq, Ollama & OpenRouter (200+ models)
```

No prompt rewriting. No altered model outputs. Just fewer tokens going out.

---

## Supported Models & Providers

| Provider | Supported Models | Routing Type |
|---|---|---|
| **xAI Grok** | `grok-4.7`, `grok-2`, `grok-beta`, `grok-2-vision` | Native OpenAI-compatible |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini`, `gpt-4`, `gpt-3.5-turbo` | Native |
| **Anthropic Claude** | `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`, `claude-3-haiku-20240307` | Bidirectional Adapter |
| **Google Gemini** | `gemini-2.0-flash`, `gemini-1.5-pro`, `gemini-1.5-flash` | Native OpenAI-compatible |
| **DeepSeek** | `deepseek-chat`, `deepseek-reasoner` (R1) | Native OpenAI-compatible |
| **Mistral AI** | `mistral-large-latest`, `codestral-latest`, `mistral-small` | Native OpenAI-compatible |
| **Groq** | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral` | Native OpenAI-compatible |
| **Local LLMs / Ollama** | Any local model running on `http://localhost:11434` | Local proxy |
| **OpenRouter** | 200+ open-source and proprietary models (`meta-llama/...`, etc.) | Gateway proxy |

---

## Quick Start

### Prerequisites
- Python 3.9 or higher
- An API key for your chosen provider (xAI Grok / OpenAI / Gemini / Anthropic / DeepSeek)

### 1. Clone the repository

```bash
git clone https://github.com/sureshsangra/AI-Token-Guard.git
cd AI-Token-Guard
```

### 2. Install dependencies

```bash
# Option A — project venv (recommended)
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Option B — editable install (registers the `token-guard` CLI command)
pip install -e .
```

> **Tip — Better accuracy:** Install `tiktoken` for exact OpenAI-spec token counts:
> ```bash
> pip install tiktoken
> ```
> Without it, Token Guard uses a fast regex heuristic (~95 % accurate) that requires zero extra dependencies.

### 3. Configure your API keys

```bash
cp .env.example .env
```

Edit `.env` and add the keys you need:

```ini
# .env — only add the keys for providers you use
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...

# Optional tuning
PRUNER_AGGRESSIVENESS=medium    # light | medium | aggressive
MAX_HISTORY_TURNS=6             # keep last N turns verbatim before condensing
SEMANTIC_CACHE_THRESHOLD=0.85   # 0.0 – 1.0 similarity threshold
```

### 4. Start the proxy

```bash
# Using the CLI (after pip install -e .)
token-guard start

# Or directly
python3 token_guard/server.py
```

You should see:

```
🛡️  Token Guard Proxy starting on http://0.0.0.0:8088
📊  Live Dashboard:   http://localhost:8088/dashboard
🔌  OpenAI Base URL:  http://localhost:8088/v1
```

Open **http://localhost:8088/dashboard** in your browser to monitor live savings.

---

## Plug-and-Play Integration

### Python — OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8088/v1",   # ← only this line changes
    api_key="your-api-key"
)

# Works with any supported model — routing is automatic
response = client.chat.completions.create(
    model="gpt-4o",          # or "gemini-2.0-flash" or "claude-3-5-sonnet-20241022"
    messages=[{"role": "user", "content": "Explain compound interest."}]
)
print(response.choices[0].message.content)
```

### Node.js / TypeScript

```ts
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:8088/v1",
  apiKey: process.env.OPENAI_API_KEY,
});

const res = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [{ role: "user", content: "Hello!" }],
});
```

### cURL

```bash
curl http://localhost:8088/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role":"user","content":"Hi!"}]
  }'
```

### LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8088/v1",
    api_key="your-key",
    model="gpt-4o"
)
```

### LlamaIndex

```python
from llama_index.llms.openai import OpenAI

llm = OpenAI(
    api_base="http://localhost:8088/v1",
    api_key="your-key",
    model="gpt-4o"
)
```

---

## IDE Integration

### Cursor
1. Open **Settings → Features → Models**.
2. Enable **Override OpenAI Base URL**.
3. Set URL: `http://localhost:8088/v1`

### VS Code — Cline / Roo Code
1. Open the extension settings.
2. **API Provider** → `OpenAI Compatible`
3. **Base URL** → `http://localhost:8088/v1`

### VS Code — Continue.dev
Add to `~/.continue/config.json`:
```json
{
  "models": [{
    "title": "Token Guard GPT-4o",
    "provider": "openai",
    "model": "gpt-4o",
    "apiBase": "http://localhost:8088/v1",
    "apiKey": "your-api-key"
  }]
}
```

---

## Browser Extension (ChatGPT / Claude / Gemini Web)

For users of the web interfaces:

1. Open `chrome://extensions` in Chrome / Brave / Edge.
2. Enable **Developer mode** (top-right toggle).
3. Click **Load unpacked** → select the `token_guard/browser_extension/` folder.

The extension auto-prunes prompts on **chatgpt.com**, **claude.ai**, and **gemini.google.com** before they are sent, and reports savings to your local dashboard.

---

## The 4-Tier Optimization Pipeline

### Tier 1 — Exact & Semantic Cache
Identical or semantically similar queries return the cached response immediately — **0 upstream tokens spent**.

- Exact cache: SHA-256 hash of the entire message payload.
- Semantic cache: Lightweight vector similarity (cosine ≥ 0.85) using an on-device bag-of-words embedding — **no external embedding API calls**.

### Tier 2 — Tool / Schema Minifier
LLM tool definitions carry large JSON schema payloads. Token Guard strips redundant fields (`$schema`, `title`, `additionalProperties`, empty `description`, whitespace) without changing semantics.

Typical savings: **30 – 60 %** on agent/tool-heavy workloads.

### Tier 3 — Conversation History Condenser
Long multi-turn dialogues repeat stale context. Token Guard keeps your system prompt and the most recent N turns verbatim, compressing older turns into a dense bullet-point summary injected as a system message.

Typical savings: **20 – 50 %** on conversations longer than 10 turns.

### Tier 4 — Prompt & Context Pruner
Removes token-wasting boilerplate from prompts and RAG-retrieved documents:
- Conversational filler ("As an AI language model…", "Please note that…")
- Excessive blank lines and trailing whitespace
- Redundant markdown dividers

Typical savings: **15 – 55 %** on verbose prompts or RAG context blocks.

---

## Response Headers

Every response from Token Guard includes savings metadata:

```
X-TokenGuard-Status:           optimized
X-TokenGuard-Original-Tokens:  820
X-TokenGuard-Optimized-Tokens: 504
X-TokenGuard-Saved-Tokens:     316
X-TokenGuard-Savings:          38.5%
```

On a cache hit:
```
X-TokenGuard-Status:      exact_cache_hit
X-TokenGuard-Savings:     100%
X-TokenGuard-Saved-Tokens: 820
```

---

## Tokenizer

The tokenizer is fully standalone and works as a library independent of the proxy:

```python
from token_guard.tokenizer import count_text_tokens, count_messages_tokens, tokenizer_info

# Single string
print(count_text_tokens("Hello, world!"))                        # 4
print(count_text_tokens("こんにちは", model="gpt-4o"))           # 6

# Full chat payload (model-aware)
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user",   "content": "What is 2 + 2?"},
]
print(count_messages_tokens(messages, model="claude-3-5-sonnet-20241022"))  # 25

# Inspect which backend is active
print(tokenizer_info())
# {
#   "backend": "tiktoken",        ← "heuristic_regex" if tiktoken not installed
#   "tiktoken_available": True,
#   "supported_models": ["gpt-4o", "gemini-2.0-flash", ...]
# }
```

**Backend priority:**

| Priority | Backend | Accuracy | Extra dependency |
|---|---|---|---|
| 1 (preferred) | `tiktoken` | Exact (OpenAI-spec) | `pip install tiktoken` |
| 2 (fallback) | Regex heuristic | ~95 % | None |

The fallback kicks in automatically if `tiktoken` is not installed — no code changes needed.

---

## Configuration Reference

All settings can be set in `.env` or as environment variables:

| Variable | Default | Description |
|---|---|---|
| `TOKEN_GUARD_PORT` | `8088` | Local proxy port |
| `TOKEN_GUARD_HOST` | `0.0.0.0` | Bind address |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `ANTHROPIC_API_KEY` | — | Anthropic Claude API key |
| `ENABLE_EXACT_CACHE` | `true` | SHA-256 exact cache |
| `ENABLE_SEMANTIC_CACHE` | `true` | Vector similarity cache |
| `SEMANTIC_CACHE_THRESHOLD` | `0.85` | Min cosine similarity for cache hit |
| `ENABLE_SCHEMA_MINIFIER` | `true` | Strip verbose tool schemas |
| `ENABLE_HISTORY_CONDENSER` | `true` | Compress old conversation turns |
| `MAX_HISTORY_TURNS` | `6` | Verbatim turns to preserve |
| `ENABLE_PROMPT_PRUNER` | `true` | Remove boilerplate from prompts |
| `PRUNER_AGGRESSIVENESS` | `medium` | `light` / `medium` / `aggressive` |

---

## Docker

```bash
# Single container
docker build -t token-guard .
docker run -d -p 8088:8088 \
  -e OPENAI_API_KEY=sk-... \
  -e GEMINI_API_KEY=AIza... \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  token-guard

# Or with docker compose
docker compose up -d
```

---

## CLI Reference

```bash
token-guard start               # start the proxy (default port 8088)
token-guard start --port 9000  # custom port
token-guard start --reload     # auto-reload on code changes (dev mode)
token-guard stats               # print current savings summary
token-guard test                # run the built-in optimization test suite
```

---

## Project Structure

```
token_guard/
├── server.py                 # FastAPI application entry point
├── cli.py                    # `token-guard` CLI commands
├── config.py                 # Settings (env-driven)
├── tokenizer.py              # Production tokenizer (tiktoken + fallback)
├── core/
│   ├── pipeline.py           # 4-tier optimization orchestrator
│   ├── cache.py              # Exact & semantic cache
│   ├── schema_minifier.py    # Tool/JSON schema compression
│   ├── history_condenser.py  # Conversation sliding window
│   ├── prompt_pruner.py      # Boilerplate & whitespace removal
│   └── storage.py            # SQLite persistence for metrics
├── adapters/
│   └── anthropic.py          # OpenAI ↔ Anthropic format translator
├── routers/
│   ├── openai_proxy.py       # /v1/chat/completions (all providers)
│   └── metrics.py            # /metrics, /simulate, /extension/log
├── dashboard/
│   └── index.html            # Live token savings dashboard
├── browser_extension/
│   ├── manifest.json         # Chrome Extension Manifest v3
│   ├── background.js         # Service worker (bypasses Mixed Content)
│   ├── content.js            # Prompt pruning on ChatGPT/Claude/Gemini
│   └── popup.html            # Extension popup UI
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml            # pip package definition
```

---

## Running Tests

```bash
# Full optimization suite
python3 token_guard/test_client.py

# Or via CLI
token-guard test
```

Expected output:
```
============================================================
🚀 RUNNING TOKEN GUARD (RTM) VERIFICATION SUITE
============================================================

[Tier 2: Schema Minifier]      Tokens Saved: 42 (29.6%)
[Tier 3: History Condenser]    Tokens Saved: 110 (22.4%)
[Tier 4: Prompt Pruner]        Tokens Saved: 45 (54.9%)
[Full Pipeline: First Request] Total Saved:  85 (13.51%)
[Exact Cache Hit]              Savings:      100.0%

✅ ALL TOKEN GUARD OPTIMIZATION TESTS PASSED PERFECTLY!
```

---

## Live Metrics API

```bash
# GET current savings summary
curl http://localhost:8088/metrics

# POST a simulated event (test the dashboard)
curl -X POST http://localhost:8088/api/simulate

# Reset all metrics
curl -X POST http://localhost:8088/metrics/reset
```

---

## Contributing

Pull requests are welcome! Please open an issue first to discuss large changes.

1. Fork the repo
2. Create your branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

Made with ❤️ to help developers spend less on tokens and more on building.

**Star ⭐ the repo if Token Guard saves you money!**

👉 **[github.com/sureshsangra/AI-Token-Guard](https://github.com/sureshsangra/AI-Token-Guard)**

</div>
