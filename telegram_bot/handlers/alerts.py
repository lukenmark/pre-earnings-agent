from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from storage.database import get_db, init_db
from storage.repositories.alert_repo import get_active_buys
from utils.formatting import score_to_emoji, format_date
from utils.logger import logger

router = Router()


@router.message(Command("alerts"))
async def cmd_alerts(message: Message) -> None:
    init_db()
    try:
        with get_db() as db:
            alerts = get_active_buys(db)
            alert_data = [{
                "ticker": a.ticker,
                "company_name": a.company_name,
                "recommendation": a.recommendation,
                "composite_score": a.composite_score,
                "earnings_date": a.earnings_date,
                "hard_veto": a.hard_veto,
                "alert_json": a.alert_json,
            } for a in alerts]
    except Exception as e:
        logger.error(f"Alerts command failed: {e}")
        await message.answer("⚠️ Failed to load alerts. Check logs.")
        return

    if not alert_data:
        await message.answer("📭 No active BUY alerts at this time.")
        return

    lines = [f"<b>🟢 Active BUY Alerts ({len(alert_data)})</b>\n"]
    for a in alert_data:
        if a["recommendation"] != "BUY":
            continue
        score_e = score_to_emoji(a["composite_score"])
        earnings_text = f" | {format_date(a['earnings_date'])}" if a.get("earnings_date") else ""
        lines.append(
            f"<b>{a['ticker']}</b> — {a['company_name'][:25]}\n"
            f"  {score_e} {a['composite_score']}/100{earnings_text}"
        )

    await message.answer("\n\n".join(lines)[:4096], parse_mode="HTML")
