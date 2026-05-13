import asyncio
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from utils.logger import logger

router = Router()


@router.message(Command("scan"))
async def cmd_scan(message: Message) -> None:
    await message.answer("🔍 Running discovery scan... (this may take 30-60 seconds)")

    loop = asyncio.get_event_loop()
    try:
        def _run_scan():
            from orchestrator.agent_orchestrator import AgentOrchestrator
            from storage.database import init_db
            init_db()
            orch = AgentOrchestrator()
            return orch.run_discovery()

        new_candidates = await loop.run_in_executor(None, _run_scan)

        if not new_candidates:
            await message.answer("✅ Scan complete. No new candidates found matching current criteria.")
            return

        lines = [f"✅ <b>Scan complete — {len(new_candidates)} new candidates added:</b>\n"]
        for c in new_candidates[:15]:
            match_icon = "🎯" if c.get("industry_match") else "📌"
            earnings_text = f" | Earnings: {c['earnings_date']}" if c.get("earnings_date") else ""
            lines.append(
                f"{match_icon} <b>{c['ticker']}</b> — score: {c.get('screen_score', 0):.0f}/100{earnings_text}"
            )
        if len(new_candidates) > 15:
            lines.append(f"...and {len(new_candidates) - 15} more")

        await message.answer("\n".join(lines)[:4096], parse_mode="HTML")

    except Exception as e:
        logger.error(f"Scan command failed: {e}")
        await message.answer(f"⚠️ Scan failed: {str(e)[:200]}")
