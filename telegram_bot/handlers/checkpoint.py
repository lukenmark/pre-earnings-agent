import asyncio
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from utils.logger import logger
from utils.formatting import score_to_emoji, decision_to_emoji

router = Router()

VALID_CHECKPOINTS = {"T-21", "T-14", "T-7", "T-3"}


@router.message(Command("checkpoint"))
async def cmd_checkpoint(message: Message) -> None:
    parts = message.text.strip().split() if message.text else []
    if len(parts) < 2:
        await message.answer("Usage: /checkpoint TICKER [T-21|T-14|T-7|T-3]\nExample: /checkpoint NVDA T-7")
        return

    ticker = parts[1].upper().strip()
    checkpoint = parts[2].upper().strip() if len(parts) >= 3 else "T-21"

    if checkpoint not in VALID_CHECKPOINTS:
        await message.answer(f"❌ Invalid checkpoint '{checkpoint}'. Use: T-21, T-14, T-7, or T-3")
        return

    await message.answer(f"📊 Running <b>{checkpoint}</b> checkpoint for <b>{ticker}</b>...", parse_mode="HTML")

    loop = asyncio.get_event_loop()
    try:
        def _run_checkpoint():
            from orchestrator.agent_orchestrator import AgentOrchestrator
            from storage.database import init_db
            init_db()
            orch = AgentOrchestrator()
            return orch.run_checkpoint(ticker, checkpoint, force=True)

        report = await loop.run_in_executor(None, _run_checkpoint)

        emoji = decision_to_emoji(report.decision)
        score_e = score_to_emoji(report.composite_score)

        delta_text = ""
        if report.score_delta is not None:
            arrow = "⬆️" if report.score_delta > 0 else ("⬇️" if report.score_delta < 0 else "➡️")
            delta_text = f" ({arrow}{report.score_delta:+d} pts)"

        factor_lines = "\n".join(
            f"  {score_to_emoji(fs.score)} {name.replace('_', ' ').title()}: {fs.score}/100"
            for name, fs in sorted(report.factor_scores.items(), key=lambda x: x[1].score, reverse=True)
        ) if report.factor_scores else "No factors scored"

        flags_text = "\n".join(f"⚠️ {f}" for f in report.flags) if report.flags else "None"

        text = (
            f"{emoji} <b>{ticker}</b> — {checkpoint}\n\n"
            f"{score_e} <b>Composite: {report.composite_score}/100</b>{delta_text}\n"
            f"Decision: <b>{report.decision}</b> | Hypothesis: {report.hypothesis_direction}\n\n"
            f"<b>Factor Scores:</b>\n{factor_lines}\n\n"
            f"<b>Flags:</b>\n{flags_text}"
        )

        # For T-3 BUY alerts, include the human confirmation keyboard
        reply_markup = None
        if checkpoint == "T-3" and report.decision == "BUY":
            from telegram_bot.keyboards import decision_keyboard
            reply_markup = decision_keyboard(ticker, checkpoint)

        await message.answer(text[:4096], parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Checkpoint command failed for {ticker} {checkpoint}: {e}")
        await message.answer(f"⚠️ Checkpoint failed for {ticker}: {str(e)[:200]}")
