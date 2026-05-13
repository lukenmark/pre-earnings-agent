#!/usr/bin/env python3
"""Phase 5 verification. Run: python3 tests/test_phase5.py"""
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

SEP = "\n" + "="*60 + "\n"

def test_providers():
    print(SEP + "PROVIDER ABSTRACTION")
    from data.factory import get_news_provider, get_options_provider, get_industry_provider
    from data.providers.base import NewsProvider, OptionsFlowProvider, IndustryDataProvider

    news = get_news_provider()
    opts = get_options_provider()
    ind = get_industry_provider()

    print(f"  News provider: {news.provider_name}")
    print(f"  Options provider: {opts.provider_name} (quality={opts.data_quality})")
    print(f"  Industry provider: {ind.provider_name}")

    # Protocol compliance
    assert isinstance(news, NewsProvider), "News provider does not implement protocol"
    assert isinstance(opts, OptionsFlowProvider), "Options provider does not implement protocol"
    assert isinstance(ind, IndustryDataProvider), "Industry provider does not implement protocol"
    print("✓ All providers implement correct Protocol")

def test_watchlist_manager():
    print(SEP + "WATCHLIST MANAGER")
    from orchestrator.watchlist_manager import WatchlistManager
    from storage.database import init_db
    init_db()

    mgr = WatchlistManager()
    industries = mgr.refresh_active_industries()
    print(f"  Active industries from DB: {industries}")

    # Check due checkpoints (may be empty if watchlist is empty)
    from datetime import date
    due = mgr.get_due_checkpoints(reference_date=date.today())
    print(f"  Due checkpoints today: {len(due)}")
    print("✓ WatchlistManager initialized and working")

def test_scheduler():
    print(SEP + "SCHEDULER")
    from orchestrator.scheduler import start_scheduler, get_scheduler_status, stop_scheduler

    sched = start_scheduler()
    assert sched.running, "Scheduler not running"

    jobs = get_scheduler_status()
    print(f"  Jobs scheduled: {len(jobs)}")
    for j in jobs:
        print(f"    - {j['name']}: next run {j['next_run']}")

    stop_scheduler()
    print("✓ Scheduler started and stopped cleanly")

def test_orchestrator_manual(ticker: str = "AAPL"):
    """
    Manual test — runs a T-21 checkpoint on AAPL without LLM.
    Shows how to manually trigger the full analysis cycle.
    """
    print(SEP + f"ORCHESTRATOR — Manual T-21 on {ticker}")
    from storage.database import init_db
    from storage.repositories.watchlist_repo import add, get_by_ticker
    from storage.database import get_db
    from models.watchlist import WatchlistEntry
    from datetime import datetime, date, timedelta, timezone

    init_db()

    # Add ticker to watchlist if not present
    with get_db() as db:
        existing = get_by_ticker(db, ticker)
        if not existing:
            entry = WatchlistEntry(
                ticker=ticker,
                company_name="Apple Inc",
                earnings_date=date.today() + timedelta(days=25),
                status="active",
                date_added=datetime.now(timezone.utc),
                eps_ttm=6.75,
                market_cap=4.3e12,
                industry="Technology",
            )
            add(db, entry)
            print(f"  Added {ticker} to watchlist (earnings in 25 days)")
        else:
            print(f"  {ticker} already in watchlist")

    print(f"  Running T-21 checkpoint (LLM calls will be skipped if no API key)...")
    from orchestrator.agent_orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()

    try:
        report = orch.run_checkpoint(ticker, "T-21", force=True)
        print(f"  Composite score: {report.composite_score}/100")
        print(f"  Decision: {report.decision}")
        print(f"  Flags: {report.flags or 'none'}")
        print(f"  Factor scores:")
        for factor, fs in report.factor_scores.items():
            print(f"    {factor:30s}: {fs.score:3d}/100")
        print(f"✓ T-21 checkpoint completed and saved to DB")
    except Exception as e:
        import traceback
        print(f"  ✗ Checkpoint failed: {e}")
        traceback.print_exc()

def test_industry_assessment():
    print(SEP + "INDUSTRY ASSESSMENT")
    from storage.database import init_db
    init_db()

    from orchestrator.agent_orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()
    assessment = orch.run_industry_assessment("Technology")
    print(f"  Industry: Technology")
    print(f"  Composite score: {assessment.composite_score}/100")
    print(f"  Status: {assessment.status}")
    print(f"  Metrics sampled: {list(assessment.metrics.keys())[:3]}...")
    print("✓ Industry assessment saved to DB")

if __name__ == "__main__":
    print("\n=== Phase 5 Orchestrator Verification ===\n")
    for fn in [test_providers, test_watchlist_manager, test_scheduler, test_industry_assessment, test_orchestrator_manual]:
        try:
            fn()
        except Exception as e:
            import traceback
            print(f"✗ {fn.__name__}: {e}")
            traceback.print_exc()
    print("\n=== Done ===")
