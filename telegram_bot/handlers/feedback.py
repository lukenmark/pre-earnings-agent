from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from storage.database import get_db, init_db
from storage.repositories.feedback_repo import save as save_feedback
from telegram_bot.keyboards import feedback_keyboard
from utils.logger import logger

router = Router()


@router.message(Command("feedback"))
async def cmd_feedback(message: Message) -> None:
    parts = message.text.strip().split() if message.text else []
    if len(parts) < 2:
        await message.answer("Usage: /feedback TICKER\nExample: /feedback NVDA")
        return

    ticker = parts[1].upper().strip()
    await message.answer(
        f"Rate your experience with <b>{ticker}</b>:",
        parse_mode="HTML",
        reply_markup=feedback_keyboard(ticker),
    )


@router.callback_query(F.data.startswith("fb:"))
async def handle_feedback_callback(callback: CallbackQuery) -> None:
    # fb:TICKER:RATING
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Invalid feedback data")
        return

    ticker = parts[1]
    try:
        rating = int(parts[2])
    except ValueError:
        await callback.answer("Invalid rating")
        return

    user_id = str(callback.from_user.id)
    stars = "⭐" * rating

    # Ask for notes via follow-up (store rating first, notes optional)
    init_db()
    try:
        with get_db() as db:
            save_feedback(db, ticker, user_id, rating, notes=None)
    except Exception as e:
        logger.error(f"Failed to save feedback for {ticker}: {e}")
        await callback.answer("Failed to save feedback")
        return

    await callback.message.edit_text(
        f"✅ Feedback saved: <b>{ticker}</b> {stars} ({rating}/5)\n"
        f"Reply to this message with notes (optional), or send /feedback {ticker} &lt;your notes&gt;",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:"))
async def handle_confirm_callback(callback: CallbackQuery) -> None:
    # confirm:TICKER:CHECKPOINT:DECISION
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Invalid confirmation data")
        return

    ticker, checkpoint, decision = parts[1], parts[2], parts[3]
    user_name = callback.from_user.full_name or callback.from_user.username or "Unknown"

    icon = "✅" if decision == "BUY" else "❌"
    await callback.message.edit_text(
        f"{icon} <b>{decision}</b> confirmed for <b>{ticker}</b> by {user_name}\n"
        f"<i>This is logged. Agent does not execute trades.</i>",
        parse_mode="HTML",
    )
    await callback.answer(f"{decision} recorded")
    logger.info(f"Human confirmed {decision} for {ticker} ({checkpoint}) by user {callback.from_user.id}")


@router.callback_query(F.data.startswith("action:"))
async def handle_action_callback(callback: CallbackQuery) -> None:
    # action:TICKER:ACTION
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    ticker, action = parts[1], parts[2]
    if action == "feedback":
        await callback.message.answer(
            f"Rate <b>{ticker}</b>:",
            parse_mode="HTML",
            reply_markup=feedback_keyboard(ticker),
        )
    elif action == "analyze":
        await callback.message.answer(f"Use: /analyze {ticker}")
    elif action == "checkpoint":
        await callback.message.answer(f"Use: /checkpoint {ticker} T-21")
    await callback.answer()
