from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from storage.database import get_db, init_db
from storage.repositories import alert_watchlist_repo
from data.yfinance_client import get_stock_info
from utils.logger import logger

router = Router()


@router.message(Command("watch"))
async def cmd_watch(message: Message) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("Usage: /watch TICKER\nExample: /watch NVDA")
        return

    ticker = args[1].strip().upper().split()[0]  # take first word if extra args given

    init_db()
    with get_db() as db:
        existing = alert_watchlist_repo.get_by_ticker(db, ticker)
        if existing:
            await message.answer(f"📡 {ticker} is already on your alert watchlist.")
            return

    await message.answer(f"🔍 Looking up {ticker}...")

    # Validate ticker and get company name
    info = {}
    try:
        info = get_stock_info(ticker) or {}
    except Exception as e:
        logger.warning(f"/watch: could not fetch info for {ticker}: {e}")

    if not info:
        await message.answer(f"⚠️ Could not find {ticker} on yfinance. Check the ticker symbol and try again.")
        return

    company_name = (
        info.get("longName")
        or info.get("shortName")
        or info.get("displayName")
        or ticker
    )

    try:
        with get_db() as db:
            alert_watchlist_repo.add(db, ticker, company_name)
        await message.answer(
            f"✅ <b>{ticker}</b> ({company_name}) added to your alert watchlist.\n\n"
            f"You'll get a daily briefing at 9 AM ET on weekdays if there's a 5%+ price move or new news.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"/watch: failed to add {ticker}: {e}")
        await message.answer(f"⚠️ Failed to add {ticker}: {str(e)[:200]}")


@router.message(Command("unwatch"))
async def cmd_unwatch(message: Message) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("Usage: /unwatch TICKER\nExample: /unwatch NVDA")
        return

    ticker = args[1].strip().upper().split()[0]

    try:
        with get_db() as db:
            removed = alert_watchlist_repo.remove(db, ticker)
        if removed:
            await message.answer(f"🗑 {ticker} removed from your alert watchlist.")
        else:
            await message.answer(f"⚠️ {ticker} wasn't on your alert watchlist.")
    except Exception as e:
        logger.error(f"/unwatch: failed to remove {ticker}: {e}")
        await message.answer(f"⚠️ Failed to remove {ticker}: {str(e)[:200]}")


@router.message(Command("watching"))
async def cmd_watching(message: Message) -> None:
    init_db()
    try:
        with get_db() as db:
            rows = alert_watchlist_repo.get_all(db)
            entries = [
                {
                    "ticker": row.ticker,
                    "company": row.company_name,
                    "added_at": row.added_at,
                    "last_checked_at": row.last_checked_at,
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"/watching: failed to load alert watchlist: {e}")
        await message.answer("⚠️ Failed to load alert watchlist.")
        return

    if not entries:
        await message.answer("📡 Your alert watchlist is empty.\n\nUse /watch TICKER to add stocks.")
        return

    lines = ["<b>📡 Alert Watchlist</b> (daily 9 AM ET check)\n"]
    for e in entries:
        added = e["added_at"].strftime("%b %d") if e["added_at"] else "?"
        last = e["last_checked_at"].strftime("%b %d %H:%M") if e["last_checked_at"] else "never"
        lines.append(f"<b>{e['ticker']}</b> — {e['company']}\n  Added {added} | Last checked {last}")

    await message.answer("\n\n".join(lines)[:4096], parse_mode="HTML")
