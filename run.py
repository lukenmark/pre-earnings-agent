#!/usr/bin/env python3
"""
Pre-Earnings Research Agent — CLI

Usage:
  python run.py scan              Run discovery scan
  python run.py analyze TICKER   Run T-21 analysis on TICKER
  python run.py checkpoint TICKER [T-21|T-14|T-7|T-3]
  python run.py bot               Start Telegram bot (no scheduler)
  python run.py start             Start bot + scheduler together
  python run.py dashboard         Launch Streamlit dashboard
  python run.py feedback TICKER   Add feedback for a ticker
  python run.py status            Show system status
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from storage.database import init_db
from utils.logger import logger


def cmd_scan():
    init_db()
    from orchestrator.agent_orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()
    results = orch.run_discovery()
    if results:
        print(f"\n✅ Added {len(results)} new candidates:")
        for r in results:
            print(f"  {r['ticker']} — score {r.get('screen_score', 0):.0f}/100, earnings: {r.get('earnings_date')}")
    else:
        print("No new candidates found.")


def cmd_analyze(ticker: str):
    init_db()
    from orchestrator.agent_orchestrator import AgentOrchestrator
    from utils.formatting import score_to_emoji, decision_to_emoji
    orch = AgentOrchestrator()
    print(f"Running T-21 analysis for {ticker}...")
    report = orch.run_checkpoint(ticker, "T-21", force=True)
    print(f"\n{'='*50}")
    print(f"{ticker} — T-21 Checkpoint")
    print(f"Composite Score: {report.composite_score}/100")
    print(f"Decision: {report.decision}")
    print(f"Hypothesis: {report.hypothesis_direction}")
    print(f"\nFactor Scores:")
    for name, fs in sorted(report.factor_scores.items(), key=lambda x: x[1].score, reverse=True):
        print(f"  {score_to_emoji(fs.score)} {name:30s}: {fs.score}/100")
    if report.flags:
        print(f"\nFlags:")
        for f in report.flags:
            print(f"  ⚠️  {f}")
    if report.key_findings:
        print(f"\nKey Findings:")
        for f in report.key_findings[:5]:
            print(f"  • {f}")


def cmd_checkpoint(ticker: str, checkpoint: str = "T-21"):
    init_db()
    from orchestrator.agent_orchestrator import AgentOrchestrator
    from utils.formatting import score_to_emoji, decision_to_emoji
    print(f"Running {checkpoint} for {ticker}...")
    orch = AgentOrchestrator()
    report = orch.run_checkpoint(ticker, checkpoint, force=True)
    print(f"\n{ticker} {checkpoint}: {report.composite_score}/100 — {report.decision}")
    for name, fs in sorted(report.factor_scores.items(), key=lambda x: x[1].score, reverse=True):
        print(f"  {name:30s}: {fs.score}")


def cmd_bot():
    """Start Telegram bot only (no scheduler)"""
    import asyncio
    from telegram_bot.bot import run_bot
    print("Starting Telegram bot...")
    asyncio.run(run_bot())


def cmd_start():
    """Start bot + scheduler together"""
    import asyncio
    from orchestrator.scheduler import start_scheduler, stop_scheduler
    from telegram_bot.bot import run_bot

    init_db()
    start_scheduler()
    print("Scheduler started.")
    print("Starting Telegram bot...")
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_scheduler()


def cmd_dashboard():
    import subprocess
    subprocess.run(["streamlit", "run", "dashboard/app.py"])


def cmd_feedback(ticker: str):
    init_db()
    from storage.database import get_db
    from storage.repositories.feedback_repo import save as save_feedback
    rating_input = input(f"Rating for {ticker} (1-5): ").strip()
    notes = input("Notes (optional): ").strip()
    try:
        rating = int(rating_input)
        assert 1 <= rating <= 5
    except (ValueError, AssertionError):
        print("Invalid rating. Enter 1-5.")
        return
    with get_db() as db:
        save_feedback(db, ticker, "cli_user", rating, notes or None)
    print(f"✅ Feedback saved: {ticker} {'⭐' * rating}")


def cmd_status():
    from orchestrator.scheduler import get_scheduler_status
    jobs = get_scheduler_status()
    if jobs:
        print("Scheduled jobs:")
        for j in jobs:
            print(f"  {j['name']}: next run {j['next_run']}")
    else:
        print("Scheduler not running (start with: python run.py start)")
    init_db()
    from storage.database import get_db
    from storage.repositories.watchlist_repo import get_all_active
    with get_db() as db:
        rows = get_all_active(db)
        print(f"Watchlist: {len(rows)} active tickers")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0].lower()
    if cmd == "scan":
        cmd_scan()
    elif cmd == "analyze" and len(args) >= 2:
        cmd_analyze(args[1].upper())
    elif cmd == "checkpoint" and len(args) >= 2:
        cp = args[2].upper() if len(args) >= 3 else "T-21"
        cmd_checkpoint(args[1].upper(), cp)
    elif cmd == "bot":
        cmd_bot()
    elif cmd == "start":
        cmd_start()
    elif cmd == "dashboard":
        cmd_dashboard()
    elif cmd == "feedback" and len(args) >= 2:
        cmd_feedback(args[1].upper())
    elif cmd == "status":
        cmd_status()
    else:
        print(__doc__)
        sys.exit(1)
