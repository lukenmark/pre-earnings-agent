from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from storage.database import get_db, init_db
from storage.repositories.watchlist_repo import get_all_active
from storage.repositories.checkpoint_repo import get_latest
from utils.formatting import score_to_emoji, decision_to_emoji, format_date
from utils.logger import logger

router = Router()


@router.message(Command("watchlist"))
async def cmd_watchlist(message: Message) -> None:
    init_db()
    try:
        with get_db() as db:
            rows = get_all_active(db)
            # Eagerly extract all needed data while session is open
            entries = []
            for row in rows:
                latest_cp = get_latest(db, row.ticker)
                entries.append({
                    "ticker": row.ticker,
                    "company": row.company_name,
                    "status": row.status,
                    "earnings_date": row.earnings_date,
                    "score": latest_cp.composite_score if latest_cp else None,
                    "decision": latest_cp.decision if latest_cp else None,
                    "checkpoint": latest_cp.checkpoint if latest_cp else None,
                })
    except Exception as e:
        logger.error(f"Watchlist command failed: {e}")
        await message.answer("⚠️ Failed to load watchlist. Check logs.")
        return

    if not entries:
        await message.answer("📋 Watchlist is empty. Use /scan to discover candidates.")
        return

    lines = ["<b>📋 Active Watchlist</b>\n"]
    for e in entries:
        score_text = f"{score_to_emoji(e['score'])} {e['score']}/100" if e['score'] is not None else "⚪ Not scored"
        decision_text = f" | {e['decision']}" if e['decision'] else ""
        earnings_text = f" | Earnings: {format_date(e['earnings_date'])}" if e['earnings_date'] else ""
        cp_text = f" | Last: {e['checkpoint']}" if e['checkpoint'] else ""
        lines.append(
            f"<b>{e['ticker']}</b> — {e['company'][:25]}\n"
            f"  {score_text}{decision_text}{cp_text}{earnings_text}"
        )

    await message.answer("\n\n".join(lines)[:4096], parse_mode="HTML")
