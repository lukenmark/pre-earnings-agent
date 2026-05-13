from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from orchestrator.scheduler import get_scheduler_status
from storage.database import get_db, init_db
from storage.repositories.watchlist_repo import get_all_active
from utils.logger import logger

router = Router()


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    init_db()

    # Scheduler status
    jobs = get_scheduler_status()
    job_lines = "\n".join(
        f"  • {j['name']}: {j['next_run'][:19] if j['next_run'] else 'not scheduled'}"
        for j in jobs
    ) if jobs else "  Scheduler not running"

    # Watchlist count
    try:
        with get_db() as db:
            active_rows = get_all_active(db)
            active_count = len(active_rows)
    except Exception:
        active_count = 0

    text = (
        f"<b>🤖 Agent Status</b>\n\n"
        f"<b>Watchlist:</b> {active_count} active tickers\n\n"
        f"<b>Scheduled Jobs:</b>\n{job_lines}\n\n"
        f"<b>Data Providers:</b>\n"
        f"  News: {__import__('os').getenv('NEWS_PROVIDER', 'yfinance')}\n"
        f"  Options: {__import__('os').getenv('OPTIONS_PROVIDER', 'estimated')}\n"
        f"  Industry: {__import__('os').getenv('INDUSTRY_PROVIDER', 'yfinance')}"
    )

    await message.answer(text[:4096], parse_mode="HTML")
