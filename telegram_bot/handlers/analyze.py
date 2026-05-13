import asyncio
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F
from utils.logger import logger
from utils.formatting import score_to_emoji, decision_to_emoji

router = Router()


@router.message(Command("analyze"))
async def cmd_analyze(message: Message) -> None:
    # Parse ticker from command args
    parts = message.text.strip().split() if message.text else []
    if len(parts) < 2:
        await message.answer("Usage: /analyze TICKER\nExample: /analyze NVDA")
        return

    ticker = parts[1].upper().strip()
    await message.answer(f"🔬 Running T-21 analysis for <b>{ticker}</b>... (may take 60-120s with LLM)", parse_mode="HTML")

    loop = asyncio.get_event_loop()
    try:
        def _run_analyze():
            from orchestrator.agent_orchestrator import AgentOrchestrator
            from storage.database import init_db
            init_db()
            orch = AgentOrchestrator()
            return orch.run_checkpoint(ticker, "T-21", force=True)

        report = await loop.run_in_executor(None, _run_analyze)

        emoji = decision_to_emoji(report.decision)
        score_e = score_to_emoji(report.composite_score)

        flags_text = "\n".join(f"⚠️ {f}" for f in report.flags[:3]) if report.flags else "None"

        factor_lines = ""
        if report.factor_scores:
            factor_lines = "\n".join(
                f"  {score_to_emoji(fs.score)} {name.replace('_', ' ').title()}: {fs.score}/100"
                for name, fs in sorted(report.factor_scores.items(), key=lambda x: x[1].score, reverse=True)
            )

        text = (
            f"{emoji} <b>{ticker}</b> — T-21 Analysis\n\n"
            f"{score_e} <b>Composite: {report.composite_score}/100</b>\n"
            f"Decision: <b>{report.decision}</b>\n"
            f"Hypothesis: {report.hypothesis_direction}\n\n"
            f"<b>Factor Scores:</b>\n{factor_lines}\n\n"
            f"<b>Key Findings:</b>\n" +
            ("\n".join(f"• {f}" for f in report.key_findings[:4]) or "None") +
            f"\n\n<b>Flags:</b>\n{flags_text}"
        )

        await message.answer(text[:4096], parse_mode="HTML")

    except Exception as e:
        logger.error(f"Analyze command failed for {ticker}: {e}")
        await message.answer(f"⚠️ Analysis failed for {ticker}: {str(e)[:200]}")
