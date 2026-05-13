from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

HELP_TEXT = """
<b>Pre-Earnings Research Agent</b>

<b>Watchlist Commands:</b>
/watchlist — Show active watchlist with scores and next checkpoint
/scan — Run Finviz discovery scan for new candidates
/alerts — Show all active BUY alerts

<b>Analysis Commands:</b>
/analyze TICKER — Run full T-21 analysis on a ticker
/checkpoint TICKER [T-21|T-14|T-7|T-3] — Run a specific checkpoint

<b>Feedback:</b>
/feedback TICKER — Rate and note a ticker outcome

<b>Info:</b>
/help — Show this message
/status — Show scheduler status and system health

<b>Scoring:</b>
🟢 Score ≥ 70 = BUY alert
🟡 Score 50-69 = WATCH
🔴 Score &lt; 50 = NO-GO
"""


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")
