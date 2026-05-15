from datetime import date

from aiogram import Router, F
from aiogram.types import Message

from storage.database import get_db
from storage.repositories.watchlist_repo import get_all_active
from storage.repositories.checkpoint_repo import get_latest
from utils.llm import complete_async
from utils.logger import logger

router = Router()

SYSTEM_PROMPT = """You are a pre-earnings stock research agent. You have deep knowledge of the stocks
currently on the watchlist and their analysis. Be direct, opinionated, and concise — the user is an
investor who wants your actual take, not hedged disclaimers.

When asked about excitement or confidence, give a real ranked opinion based on the data you have:
composite scores, decision signals, earnings proximity, and sector context. If no checkpoint analysis
has run yet, reason from the screening data and earnings date timing."""


def _build_watchlist_context(entries: list[dict]) -> str:
    if not entries:
        return "The watchlist is currently empty."

    today = date.today()
    lines = ["Current watchlist:"]
    for e in entries:
        ed = e["earnings_date"]
        days_out = (ed - today).days if ed else None
        days_str = f"{days_out}d to earnings" if days_out is not None else "earnings date unknown"

        score_str = f"score={e['score']}/100" if e["score"] is not None else "not yet scored"
        decision_str = f"decision={e['decision']}" if e["decision"] else "no decision yet"
        cp_str = f"last checkpoint={e['checkpoint']}" if e["checkpoint"] else "no checkpoint run"
        screen_str = f"screen_score={e['screen_score']}" if e.get("screen_score") is not None else ""

        lines.append(
            f"- {e['ticker']} ({e['company']}): {days_str} | {score_str} | {decision_str} | {cp_str}"
            + (f" | {screen_str}" if screen_str else "")
            + (f" | status={e['status']}" if e["status"] != "candidate" else "")
        )
    return "\n".join(lines)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_chat(message: Message) -> None:
    user_text = (message.text or "").strip()
    if not user_text:
        return

    # Load watchlist context
    try:
        with get_db() as db:
            rows = get_all_active(db)
            entries = []
            for row in rows:
                latest_cp = get_latest(db, row.ticker)
                # Parse screen_score from notes field
                screen_score = None
                if row.notes:
                    for part in row.notes.split(","):
                        if "screen_score=" in part:
                            try:
                                screen_score = float(part.split("=")[1].strip())
                            except (ValueError, IndexError):
                                pass
                entries.append({
                    "ticker": row.ticker,
                    "company": row.company_name,
                    "status": row.status,
                    "earnings_date": row.earnings_date,
                    "score": latest_cp.composite_score if latest_cp else None,
                    "decision": latest_cp.decision if latest_cp else None,
                    "checkpoint": latest_cp.checkpoint if latest_cp else None,
                    "screen_score": screen_score,
                })
    except Exception as e:
        logger.error(f"Chat handler failed to load watchlist: {e}")
        await message.answer("⚠️ Couldn't load watchlist context.")
        return

    context = _build_watchlist_context(entries)
    user_message = f"{context}\n\nUser question: {user_text}"

    thinking_msg = await message.answer("💭 Thinking...")

    try:
        reply = await complete_async(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            operation_name="telegram_chat",
            use_haiku=False,
            max_tokens=1024,
        )
        await thinking_msg.delete()
        # Telegram HTML parse mode is active by default; send as plain text to avoid tag issues
        for chunk in _split(reply, 4096):
            await message.answer(chunk, parse_mode=None)
    except Exception as e:
        logger.error(f"Chat handler LLM call failed: {e}")
        await thinking_msg.edit_text(f"⚠️ Failed to generate response: {str(e)[:200]}")


def _split(text: str, limit: int) -> list[str]:
    chunks = []
    while len(text) > limit:
        chunks.append(text[:limit])
        text = text[limit:]
    if text:
        chunks.append(text)
    return chunks
