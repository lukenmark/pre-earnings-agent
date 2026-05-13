import asyncio
import os
from typing import Callable
from aiogram import Bot
from models.checkpoint import CheckpointReport
from models.alert import FinalAlert
from utils.formatting import score_to_emoji, decision_to_emoji, format_score, format_date
from utils.logger import logger


async def send_checkpoint_notification(bot: Bot, report: CheckpointReport, chat_id: str) -> None:
    """Push a checkpoint summary to the group chat"""
    emoji = decision_to_emoji(report.decision)
    score_e = score_to_emoji(report.composite_score)

    flags_text = ""
    if report.flags:
        flags_text = "\n".join(f"⚠️ {f}" for f in report.flags[:3])
        flags_text = f"\n\n{flags_text}"

    delta_text = ""
    if report.score_delta is not None:
        arrow = "⬆️" if report.score_delta > 0 else ("⬇️" if report.score_delta < 0 else "➡️")
        delta_text = f" ({arrow}{abs(report.score_delta):+d} from prior)"

    factor_lines = ""
    if report.factor_scores:
        top_factors = sorted(report.factor_scores.items(), key=lambda x: x[1].score, reverse=True)
        factor_lines = "\n".join(
            f"  {score_to_emoji(fs.score)} {name.replace('_', ' ').title()}: {fs.score}/100"
            for name, fs in top_factors[:4]
        )
        factor_lines = f"\n\n<b>Top Factors:</b>\n{factor_lines}"

    text = (
        f"{emoji} <b>{report.ticker}</b> — {report.checkpoint} Complete\n"
        f"{score_e} Score: <b>{report.composite_score}/100</b>{delta_text}\n"
        f"Decision: <b>{report.decision}</b>"
        f"{flags_text}"
        f"{factor_lines}"
    )

    try:
        await bot.send_message(chat_id=chat_id, text=text[:4096], parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send checkpoint notification for {report.ticker}: {e}")


async def send_buy_alert(bot: Bot, alert: FinalAlert, chat_id: str) -> None:
    """Push a BUY alert to the group chat with human-in-the-loop confirmation keyboard"""
    from telegram_bot.keyboards import decision_keyboard

    trajectory_str = " → ".join(str(s) for s in alert.checkpoint_trajectory) if alert.checkpoint_trajectory else "N/A"
    veto_warning = "\n🚫 <b>HARD VETO</b> — Heavy insider selling detected" if alert.hard_veto else ""

    text = (
        f"🟢 <b>BUY ALERT: {alert.ticker}</b> — {alert.company_name}\n\n"
        f"📊 Composite: <b>{alert.composite_score}/100</b>\n"
        f"📈 Trajectory: {trajectory_str}\n"
        f"🗓 Earnings: <b>{format_date(alert.earnings_date)}</b>\n\n"
        f"<b>Thesis:</b> {alert.thesis}\n\n"
        f"<b>Core Scores:</b>\n"
        f"  📰 News Quality: {alert.core_news_score}/100\n"
        f"  💰 Price Absorption: {alert.core_pag_score}/100\n"
        f"  👤 Insider Activity: {alert.insider_summary[:80]}...\n"
        f"  📊 Options Flow: {alert.options_snapshot[:80]}..."
        f"{veto_warning}"
    )

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text[:4096],
            parse_mode="HTML",
            reply_markup=decision_keyboard(alert.ticker, "T-3") if not alert.hard_veto else None,
        )
    except Exception as e:
        logger.error(f"Failed to send BUY alert for {alert.ticker}: {e}")


async def send_no_go_notification(bot: Bot, ticker: str, reason: str, chat_id: str) -> None:
    text = f"🔴 <b>NO-GO: {ticker}</b>\n{reason}"
    try:
        await bot.send_message(chat_id=chat_id, text=text[:4096], parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send NO-GO notification for {ticker}: {e}")


async def send_simple_message(bot: Bot, chat_id: str, text: str) -> None:
    try:
        await bot.send_message(chat_id=chat_id, text=text[:4096], parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
