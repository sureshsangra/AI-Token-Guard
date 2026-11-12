"""Command Line Interface (CLI) for Token Guard."""
import sys
import os

# Ensure parent directory is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import click
import uvicorn
from token_guard.config import settings

@click.group()
def main():
    """🛡️ Token Guard - Universal AI Token Optimization CLI."""
    pass

@main.command()
@click.option("--host", default=settings.HOST, help="Host to bind to.")
@click.option("--port", default=settings.PORT, help="Port to listen on.")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload on code changes.")
def start(host, port, reload):
    """Start the Token Guard Proxy server and Live Dashboard."""
    click.echo(click.style(f"\n🛡️  Token Guard Proxy starting on http://{host}:{port}", fg="cyan", bold=True))
    click.echo(click.style(f"📊  Live Dashboard: http://localhost:{port}/dashboard", fg="green"))
    click.echo(click.style(f"🔌  OpenAI Base URL: http://localhost:{port}/v1\n", fg="yellow"))
    uvicorn.run("token_guard.server:app", host=host, port=port, reload=reload)

@main.command()
@click.option("--port", default=settings.PORT, help="Port of running proxy.")
def stats(port):
    """Print current token savings and metrics."""
    import httpx
    try:
        res = httpx.get(f"http://localhost:{port}/metrics", timeout=5.0)
        data = res.json()
        click.echo("\n--- 🛡️ Token Guard Savings Summary ---")
        click.echo(f"Total Requests:     {data['total_requests']}")
        click.echo(f"Tokens Saved:       {data['total_tokens_saved']:,}")
        click.echo(f"Average Reduction:  {data['overall_savings_percentage']}%")
        click.echo(f"Estimated Savings:  ${data['estimated_dollars_saved']:.4f}")
        click.echo(f"Cache Hits:         {data['cache_hits']}\n")
    except Exception as e:
        click.echo(click.style(f"Could not reach Token Guard on port {port}. Is the server running?", fg="red"))

@main.command()
def test():
    """Run internal optimization and compression tests."""
    from token_guard.test_client import run_tests
    run_tests()

if __name__ == "__main__":
    main()
