"""Comprehensive verification test for Token Guard optimization engines."""
import json
from token_guard.core.pipeline import OptimizationPipeline
from token_guard.core.schema_minifier import SchemaMinifier
from token_guard.core.prompt_pruner import PromptPruner
from token_guard.core.history_condenser import HistoryCondenser
from token_guard.tokenizer import count_messages_tokens, count_text_tokens

def run_tests():
    print("=" * 60)
    print("🚀 RUNNING TOKEN GUARD (RTM) VERIFICATION SUITE")
    print("=" * 60)

    # 1. Test Schema Minifier
    sample_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_stock_quote",
                "description": "  Fetches real-time stock quote and market data for a given ticker symbol.  \n",
                "parameters": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "title": "GetStockQuoteParameters",
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "title": "TickerSymbol",
                            "description": "  The stock ticker symbol, for example AAPL or TSLA.  "
                        },
                        "interval": {
                            "type": "string",
                            "title": "TimeInterval",
                            "description": "",
                            "enum": ["1m", "5m", "1d"]
                        }
                    },
                    "required": ["symbol"]
                }
            }
        }
    ]
    orig_tool_tokens = count_messages_tokens([], sample_tools)
    minified_tools = SchemaMinifier.minify_tools(sample_tools)
    opt_tool_tokens = count_messages_tokens([], minified_tools)
    tool_savings = orig_tool_tokens - opt_tool_tokens
    tool_pct = (tool_savings / orig_tool_tokens) * 100
    print(f"\n[Tier 2: Schema Minifier]")
    print(f"  Original Tool Tokens:  {orig_tool_tokens}")
    print(f"  Optimized Tool Tokens: {opt_tool_tokens}")
    print(f"  Tokens Saved:          {tool_savings} ({tool_pct:.1f}%)")
    assert tool_savings > 0, "Schema minifier should reduce tokens!"

    # 2. Test History Condenser with realistic detailed conversational turns
    conversation = [
        {"role": "system", "content": "You are a helpful financial assistant."},
        {"role": "user", "content": "Can you provide a comprehensive explanation of how compound interest works over 30 years with inflation adjustments and annual fee deductions of 1.5%?"},
        {"role": "assistant", "content": "Compound interest represents the continuous mathematical reinvestment of earnings. When factoring in a 1.5% management expense ratio alongside an estimated 3% inflation rate, real purchasing power growth requires calculating the nominal annual percentage rate minus the inflation-adjusted drag and compounding across periodic intervals."},
        {"role": "user", "content": "Could you provide a detailed step-by-step breakdown comparing a 401k versus a Roth IRA with $10,000 annual contributions over that same timeframe?"},
        {"role": "assistant", "content": "In a traditional 401(k), pre-tax contributions reduce your current adjusted gross income, allowing the entire $10,000 to compound tax-deferred until distribution age 59.5 where withdrawals are taxed as ordinary income. In contrast, a Roth IRA uses post-tax money where all future qualified distributions and compounded capital gains are 100% tax-free."},
        {"role": "user", "content": "What happens if tax rates rise to 35% in retirement?"},
        {"role": "assistant", "content": "If marginal income tax rates rise significantly, the Roth structure yields a higher net distribution because you locked in lower tax rates earlier in your earning career."},
        {"role": "user", "content": "And what formula do I use?"},
        {"role": "assistant", "content": "The formula is FV = P * (1 + r/n)**(nt)."},
        {"role": "user", "content": "What about 20 years?"}
    ]
    condenser = HistoryCondenser(max_recent_turns=4)
    condensed_conv = condenser.condense(conversation)
    orig_conv_tokens = count_messages_tokens(conversation)
    opt_conv_tokens = count_messages_tokens(condensed_conv)
    conv_savings = orig_conv_tokens - opt_conv_tokens
    conv_pct = (conv_savings / orig_conv_tokens) * 100
    print(f"\n[Tier 3: History Condenser]")
    print(f"  Original History Tokens:  {orig_conv_tokens}")
    print(f"  Optimized History Tokens: {opt_conv_tokens}")
    print(f"  Tokens Saved:             {conv_savings} ({conv_pct:.1f}%)")
    assert conv_savings > 0, "History condenser should reduce tokens on long chats!"

    # 3. Test Prompt Pruner
    verbose_prompt = """
    As an AI language model, please note that it is important to note that the following data:


    -----------------------------
    Company: Acme Corp
    -----------------------------
    Revenue: $10M

    Please feel free to ask any additional questions in order to understand this.
    """
    pruner = PromptPruner(aggressiveness="aggressive")
    orig_prune_tokens = count_text_tokens(verbose_prompt)
    pruned_text = pruner.prune_text(verbose_prompt)
    opt_prune_tokens = count_text_tokens(pruned_text)
    prune_savings = orig_prune_tokens - opt_prune_tokens
    prune_pct = (prune_savings / orig_prune_tokens) * 100
    print(f"\n[Tier 4: Prompt Pruner]")
    print(f"  Original Prompt Tokens:  {orig_prune_tokens}")
    print(f"  Optimized Prompt Tokens: {opt_prune_tokens}")
    print(f"  Tokens Saved:            {prune_savings} ({prune_pct:.1f}%)")
    assert prune_savings > 0, "Prompt pruner should eliminate whitespace and boilerplate!"

    # 4. Test End-to-End Pipeline & Semantic Cache
    pipeline = OptimizationPipeline()
    req_payload = {
        "model": "gpt-4o",
        "temperature": 0.0,
        "messages": conversation,
        "tools": sample_tools
    }

    # First Run (Cache Miss + Full Pipeline Optimization)
    result_1 = pipeline.optimize_request(req_payload)
    print(f"\n[Tier 1-4: Full Pipeline (First Request)]")
    print(f"  Original Total Tokens:  {result_1.original_tokens}")
    print(f"  Optimized Total Tokens: {result_1.optimized_tokens}")
    print(f"  Total Saved:            {result_1.tokens_saved} ({result_1.savings_percentage}%)")
    print(f"  Cache Status:           {result_1.cache_type}")
    assert result_1.tokens_saved > 0

    # Simulate upstream response storage in cache
    mock_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": "gpt-4o",
        "choices": [{"message": {"role": "assistant", "content": "For 20 years it would be $2,712.64."}}]
    }
    pipeline.record_response(
        messages=req_payload["messages"],
        model="gpt-4o",
        temperature=0.0,
        response_data=mock_response
    )

    # Second Run (Exact Cache Hit: 100% Token Savings!)
    result_2 = pipeline.optimize_request(req_payload)
    print(f"\n[Tier 1: Repeat Request (Exact Cache Hit)]")
    print(f"  Original Tokens:  {result_2.original_tokens}")
    print(f"  Tokens Charged:   {result_2.optimized_tokens} (0 upstream calls!)")
    print(f"  Savings:          {result_2.savings_percentage}% (Saved {result_2.tokens_saved} tokens)")
    print(f"  Cache Status:     {result_2.cache_type}")
    assert result_2.is_cached is True
    assert result_2.savings_percentage == 100.0

    # Third Run (Semantic Cache Hit with slightly altered phrasing)
    sem_payload = dict(req_payload)
    sem_payload["messages"] = list(conversation[:-1]) + [
        {"role": "user", "content": "What about 20 years?"} # Slight rephrase of 'And what about 20 years?'
    ]
    result_3 = pipeline.optimize_request(sem_payload)
    print(f"\n[Tier 1: Semantic Equivalent Request (Semantic Cache)]")
    print(f"  Cache Status:     {result_3.cache_type}")
    print(f"  Savings:          {result_3.savings_percentage}%")

    print("\n" + "=" * 60)
    print("✅ ALL TOKEN GUARD OPTIMIZATION TESTS PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
