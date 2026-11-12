"""FastAPI application entrypoint for Token Guard Proxy."""
import os
import sys

# Ensure parent directory is in sys.path so 'token_guard' package is always found
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

# Auto-detect project virtualenv if dependencies are missing in system python
try:
    import fastapi
    import uvicorn
except ModuleNotFoundError:
    venv_python = os.path.join(PARENT_DIR, "venv", "bin", "python")
    if os.path.exists(venv_python) and sys.executable != venv_python:
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        print("\n[Error] Missing required packages ('fastapi', 'uvicorn', etc.).")
        print("Please activate your virtual environment:")
        print("  source ../venv/bin/activate")
        print("Or install the requirements:")
        print("  pip install fastapi uvicorn httpx pydantic numpy\n")
        sys.exit(1)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from token_guard.routers.openai_proxy import router as openai_router
from token_guard.routers.metrics import router as metrics_router
from token_guard.core.prompt_pruner import PromptPruner
from token_guard.tokenizer import count_text_tokens
from token_guard.config import settings

app = FastAPI(
    title="Token Guard Proxy (RTM)",
    description="Universal Plug-and-Play Token Optimization Proxy for OpenAI, Gemini, and Claude",
    version="1.0.0"
)

# Enable CORS for web apps and extensions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(openai_router)
app.include_router(metrics_router)

# Mount Dashboard
DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    return FileResponse(DASHBOARD_PATH)

class PruneTestRequest(BaseModel):
    text: str

@app.post("/test/prune")
async def test_prune(req: PruneTestRequest):
    pruner = PromptPruner(aggressiveness="aggressive")
    orig_tokens = count_text_tokens(req.text)
    compressed = pruner.prune_text(req.text)
    comp_tokens = count_text_tokens(compressed)
    saved = max(0, orig_tokens - comp_tokens)
    pct = round((saved / orig_tokens * 100.0), 2) if orig_tokens > 0 else 0.0

    return {
        "original_tokens": orig_tokens,
        "compressed_tokens": comp_tokens,
        "saved_tokens": saved,
        "savings_percentage": pct,
        "compressed_text": compressed
    }

if __name__ == "__main__":
    import uvicorn
    print(f"\n🛡️  Starting Token Guard Proxy on http://localhost:{settings.PORT}")
    print(f"📊  Live Dashboard: http://localhost:{settings.PORT}/dashboard")
    print(f"🔌  Drop-in OpenAI Endpoint: http://localhost:{settings.PORT}/v1\n")
    uvicorn.run("token_guard.server:app", host=settings.HOST, port=settings.PORT, reload=True)
