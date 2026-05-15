import asyncio
import os
from datetime import datetime, timezone

from data.yfinance_client import get_price_history, get_stock_info
from data.news_fetcher import get_company_news
from storage.database import get_db
from storage.repositories import alert_watchlist_repo
from utils.logger import logger

PRICE_THRESHOLD_PCT = 5.0

SYSTEM_PROMPT = (
    "You are a stock market analyst giving a quick briefing. Be direct, skip disclaimers, "
    "lead with the most important thing. Write 3-5 sentences max as if texting a friend who "
    "asked 'what's up with this stock today?'"
)


def _build_user_message(ticker: str, company_name: str, pct_change: float | None, news: list[dict], trigger: str) -> str:
    lines = [f"Stock: {ticker} ({company_name})", f"Trigger: {trigger}"]

    if pct_change is not None:
        direction = "up" if pct_change >= 0 else "down"
        lines.append(f"Price move: {direction} {abs(pct_change):.1f}% from yesterday's close")

    if news:
        lines.append(f"\nRecent news ({len(news)} articles):")
        for item in news[:5]:
            date_str = item.get("published_date", "")[:10]
            lines.append(f"- [{date_str}] {item.get('headline', '')}")
    else:
        lines.append("\nNo news found in the past 24 hours.")

    return "\n".join(lines)


def _send_telegram(ticker: str, trigger: str, analysis: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_GROUP_CHAT_ID", "")
    if not token or not chat_id:
        return

    direction_icon = "📈" if "price" in trigger.lower() and "+" in trigger else "📡"
    text = f"{direction_icon} {ticker} update — {trigger}\n\n{analysis}"

    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4096]},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"alert_monitor: Telegram send failed for {ticker}: {e}")


def _check_ticker(ticker: str, company_name: str) -> None:
    triggers = []
    pct_change = None
    news = []

    # Price check
    try:
        hist = get_price_history(ticker, period="5d")
        if hist and len(hist["closes"]) >= 2:
            prev_close = hist["closes"][-2]
            today_close = hist["closes"][-1]
            if prev_close and prev_close != 0:
                pct_change = (today_close - prev_close) / prev_close * 100
                if abs(pct_change) >= PRICE_THRESHOLD_PCT:
                    sign = "+" if pct_change >= 0 else ""
                    triggers.append(f"price {sign}{pct_change:.1f}%")
    except Exception as e:
        logger.warning(f"alert_monitor: price fetch failed for {ticker}: {e}")

    # News check
    try:
        news = get_company_news(ticker, company_name, days_back=1)
        if news:
            triggers.append(f"{len(news)} new article{'s' if len(news) != 1 else ''}")
    except Exception as e:
        logger.warning(f"alert_monitor: news fetch failed for {ticker}: {e}")

    if not triggers:
        logger.info(f"alert_monitor: no trigger for {ticker}")
        return

    trigger_str = " / ".join(triggers)
    logger.info(f"alert_monitor: triggered for {ticker} — {trigger_str}")

    # LLM briefing
    try:
        from utils.llm import get_llm_client
        client = get_llm_client()
        user_msg = _build_user_message(ticker, company_name, pct_change, news, trigger_str)
        analysis = client.complete(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_msg,
            operation_name=f"alert_monitor_{ticker}",
            use_haiku=True,
            max_tokens=512,
        )
        _send_telegram(ticker, trigger_str, analysis)
    except Exception as e:
        logger.error(f"alert_monitor: LLM call failed for {ticker}: {e}")


def run_alert_check() -> None:
    logger.info("alert_monitor: starting daily alert check")
    with get_db() as db:
        entries = alert_watchlist_repo.get_all(db)
        tickers = [(row.ticker, row.company_name) for row in entries]

    if not tickers:
        logger.info("alert_monitor: alert watchlist is empty")
        return

    for ticker, company_name in tickers:
        try:
            _check_ticker(ticker, company_name)
        except Exception as e:
            logger.error(f"alert_monitor: unhandled error for {ticker}: {e}")
        finally:
            with get_db() as db:
                alert_watchlist_repo.update_last_checked(db, ticker)

    logger.info(f"alert_monitor: checked {len(tickers)} tickers")
