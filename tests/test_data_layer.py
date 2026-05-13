#!/usr/bin/env python3
"""Manual integration test for Phase 3 data layer. Run directly: python tests/test_data_layer.py"""
import sys
sys.path.insert(0, '.')


def test_cache():
    from data.cache import get, set, make_key
    set(make_key("test", "key"), {"hello": "world"}, "prices")
    result = get(make_key("test", "key"))
    assert result == {"hello": "world"}, f"Cache test failed: {result}"
    print("✓ cache: set/get works")


def test_yfinance():
    from data.yfinance_client import get_market_cap, get_quarterly_price_change, get_stock_info
    mc = get_market_cap("AAPL")
    assert mc is not None and mc > 0
    print(f"✓ yfinance: AAPL market_cap = ${mc/1e9:.1f}B")
    chg = get_quarterly_price_change("AAPL")
    print(f"✓ yfinance: AAPL 90-day price change = {chg:.1f}%")


def test_edgar():
    from data.edgar_client import get_cik, get_recent_filings
    cik = get_cik("AAPL")
    print(f"✓ edgar: AAPL CIK = {cik}")
    filings = get_recent_filings("AAPL", "10-Q", count=3)
    print(f"✓ edgar: found {len(filings)} recent 10-Q filings")
    if filings:
        print(f"  latest: {filings[0].get('filing_date')} — {filings[0].get('form_type')}")


def test_news():
    from data.news_fetcher import get_company_news
    news = get_company_news("NVDA", "NVIDIA", days_back=30)
    print(f"✓ news: found {len(news)} NVDA news items in last 30 days")
    if news:
        print(f"  sample: {news[0]['headline'][:80]}")


def test_options():
    from data.options_fetcher import get_options_metrics
    metrics = get_options_metrics("AAPL")
    if metrics:
        print(f"✓ options: AAPL data_quality={metrics['data_quality']}, C/P ratio={metrics['call_put_ratio']:.2f}")
    else:
        print("⚠ options: returned None (may be market hours issue)")


def test_finviz():
    from data.finviz_screener import run_finviz_screen
    candidates = run_finviz_screen()
    print(f"✓ finviz: screener returned {len(candidates)} candidates")
    if candidates:
        print(f"  sample: {candidates[0]}")


def test_llm():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠ llm: ANTHROPIC_API_KEY not set — skipping")
        return
    from utils.llm import LLMClient
    client = LLMClient()
    result = client.complete(
        system_prompt="You are a helpful assistant.",
        user_message="Reply with exactly: PHASE3_OK",
        operation_name="test",
        use_haiku=True,
        max_tokens=20,
    )
    assert "PHASE3_OK" in result, f"Unexpected response: {result}"
    stats = client.get_session_stats()
    print(f"✓ llm: response='{result.strip()}', tokens={stats['total_tokens']}, cost=${stats['total_cost']:.6f}")
    client.log_session_summary()


if __name__ == "__main__":
    print("\n=== Phase 3 Data Layer Verification ===\n")
    for fn in [test_cache, test_yfinance, test_edgar, test_news, test_options, test_finviz, test_llm]:
        try:
            fn()
        except Exception as e:
            print(f"✗ {fn.__name__}: {e}")
    print("\n=== Done ===")
