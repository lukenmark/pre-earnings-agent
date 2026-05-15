import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter
from aiogram.types import Message, Update
from aiogram.fsm.storage.memory import MemoryStorage

from telegram_bot.handlers import help, watchlist, scan, analyze, checkpoint, alerts, feedback, status, price_watch, chat
from utils.logger import logger

load_dotenv()

# ── Auth filter ───────────────────────────────────────────────

class AuthFilter(BaseFilter):
    """Allow only messages from the configured group chat or allowed user IDs"""

    async def __call__(self, message: Message) -> bool:
        group_chat_id = os.getenv("TELEGRAM_GROUP_CHAT_ID", "")
        allowed_ids_raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
        allowed_ids = {uid.strip() for uid in allowed_ids_raw.split(",") if uid.strip()}

        chat_id = str(message.chat.id)
        user_id = str(message.from_user.id) if message.from_user else ""

        # Allow if: message is from the group chat, OR user is in allowlist
        if group_chat_id and chat_id == group_chat_id:
            return True
        if user_id in allowed_ids:
            return True

        logger.warning(f"Unauthorized access attempt: chat={chat_id}, user={user_id}")
        return False


def create_bot() -> Bot:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
    from aiogram.client.default import DefaultBotProperties
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    auth = AuthFilter()

    # Register all routers with auth filter applied at router level
    # chat.router must be last — it catches all non-command text messages
    for router in [
        help.router,
        watchlist.router,
        scan.router,
        analyze.router,
        checkpoint.router,
        alerts.router,
        feedback.router,
        status.router,
        price_watch.router,
        chat.router,
    ]:
        router.message.filter(auth)
        dp.include_router(router)

    return dp


async def run_bot() -> None:
    """Start the bot in polling mode"""
    bot = create_bot()
    dp = create_dispatcher()

    logger.info("Starting Telegram bot (polling mode)...")

    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await bot.session.close()
        logger.info("Bot stopped")


# ── Notification helpers (sync wrappers for use from scheduler) ───────────────

def notify_checkpoint_sync(report, chat_id: str | None = None) -> None:
    """Sync wrapper — called from APScheduler jobs which are not async"""
    cid = chat_id or os.getenv("TELEGRAM_GROUP_CHAT_ID", "")
    if not cid:
        return
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    try:
        import requests
        from utils.formatting import score_to_emoji, decision_to_emoji
        emoji = decision_to_emoji(report.decision)
        score_e = score_to_emoji(report.composite_score)
        flags_text = "\n".join(f"⚠️ {f}" for f in report.flags[:2]) if report.flags else ""
        text = (
            f"{emoji} {report.ticker} — {report.checkpoint}\n"
            f"{score_e} {report.composite_score}/100 | {report.decision}\n"
            f"{flags_text}"
        ).strip()
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": cid, "text": text[:4096]},
            timeout=5,
        )
    except Exception as e:
        logger.error(f"notify_checkpoint_sync failed: {e}")
