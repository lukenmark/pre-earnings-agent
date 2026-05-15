from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from utils.logger import logger

_scheduler: BackgroundScheduler | None = None


def _job_discovery():
    """Run discovery scan every 2-3 days"""
    logger.info("Scheduler: running discovery scan")
    try:
        from orchestrator.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator()
        new_candidates = orch.run_discovery()
        logger.info(f"Scheduler: discovery added {len(new_candidates)} new candidates")
    except Exception as e:
        logger.error(f"Scheduler: discovery failed: {e}")


def _job_checkpoint_check():
    """Every morning at 7am: check if any watchlist tickers are due for a checkpoint today."""
    logger.info("Scheduler: checking for due checkpoints")
    try:
        from orchestrator.agent_orchestrator import AgentOrchestrator
        from orchestrator.watchlist_manager import WatchlistManager
        mgr = WatchlistManager()
        due = mgr.get_due_checkpoints()
        if not due:
            logger.info("Scheduler: no checkpoints due today")
            return

        orch = AgentOrchestrator()
        for item in due:
            ticker = item["ticker"]
            checkpoint = item["checkpoint"]
            logger.info(f"Scheduler: running {checkpoint} for {ticker}")
            try:
                report = orch.run_checkpoint(ticker, checkpoint)
                logger.info(f"Scheduler: {ticker} {checkpoint} → {report.decision} ({report.composite_score})")
                _notify_checkpoint(ticker, report)
            except Exception as e:
                logger.error(f"Scheduler: checkpoint {checkpoint} failed for {ticker}: {e}")
    except Exception as e:
        logger.error(f"Scheduler: checkpoint check failed: {e}")


def _job_alert_watchlist_check():
    """Daily at 9:00 AM ET: check alert watchlist for price/news triggers"""
    logger.info("Scheduler: running alert watchlist check")
    try:
        from orchestrator.alert_monitor import run_alert_check
        run_alert_check()
    except Exception as e:
        logger.error(f"Scheduler: alert watchlist check failed: {e}")


def _job_earnings_date_refresh():
    """Weekly: refresh earnings dates for all active watchlist tickers"""
    logger.info("Scheduler: refreshing earnings dates")
    try:
        from orchestrator.watchlist_manager import WatchlistManager
        mgr = WatchlistManager()
        mgr.refresh_earnings_dates()
    except Exception as e:
        logger.error(f"Scheduler: earnings date refresh failed: {e}")


def _notify_checkpoint(ticker: str, report) -> None:
    """Best-effort Telegram notification — fails silently if bot not configured"""
    try:
        import os
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_GROUP_CHAT_ID")
        if not token or not chat_id:
            return

        from utils.formatting import score_to_emoji, decision_to_emoji
        emoji = decision_to_emoji(report.decision)
        msg = (
            f"{emoji} *{ticker}* — {report.checkpoint} Complete\n"
            f"Score: {report.composite_score}/100 | Decision: {report.decision}\n"
        )
        if report.flags:
            msg += f"⚠️ {report.flags[0]}\n"

        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass  # notifications are best-effort


def start_scheduler() -> BackgroundScheduler:
    """Initialize and start the APScheduler background scheduler"""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="America/New_York")

    # Discovery scan: every 2 days at 6:00 AM ET
    _scheduler.add_job(
        _job_discovery,
        trigger=CronTrigger(hour=6, minute=0, day_of_week="mon,wed,fri"),
        id="discovery_scan",
        name="Discovery Scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Checkpoint check: every weekday at 7:00 AM ET
    _scheduler.add_job(
        _job_checkpoint_check,
        trigger=CronTrigger(hour=7, minute=0, day_of_week="mon-fri"),
        id="checkpoint_check",
        name="Checkpoint Check",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Earnings date refresh: every Sunday at 5:00 AM ET
    _scheduler.add_job(
        _job_earnings_date_refresh,
        trigger=CronTrigger(hour=5, minute=0, day_of_week="sun"),
        id="earnings_refresh",
        name="Earnings Date Refresh",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    # Alert watchlist check: every weekday at 9:00 AM ET
    _scheduler.add_job(
        _job_alert_watchlist_check,
        trigger=CronTrigger(hour=9, minute=0, day_of_week="mon-fri"),
        id="alert_watchlist_check",
        name="Alert Watchlist Check",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info("Scheduler started: discovery Mon/Wed/Fri 6AM, checkpoints weekdays 7AM, alert watchlist weekdays 9AM, earnings refresh Sun 5AM")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_scheduler_status() -> list[dict]:
    """Returns list of scheduled jobs with next run times"""
    if not _scheduler or not _scheduler.running:
        return []
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        for job in _scheduler.get_jobs()
    ]
