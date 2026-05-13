import json
from datetime import date
from models.scores import FactorScore
from utils.llm import get_llm_client
from utils.prompts import NEWS_TIERING_SYSTEM, NEWS_TIERING_USER
from utils.logger import logger
from data.news_fetcher import get_company_news, get_news_for_quarter
from orchestrator.fiscal_calendar import FiscalCalendar, FiscalQuarter


def tier_news_with_llm(
    ticker: str,
    company_name: str,
    current_fq: FiscalQuarter,
    prior_fq: FiscalQuarter,
    sources: list[str] = [],
) -> dict:
    """
    Fetches news for current and prior fiscal quarters, classifies with LLM.

    Returns dict ready to pass to score_news_quality():
    {
        "current_quarter_news": [{"tier": int, "headline": str, "date": str}],
        "prior_quarter_news": [...],
        "composition_shift": str | None,
        "llm_reasoning": str,
        "sources": list[str],
    }
    """
    # 1. Fetch news for both quarters
    current_news_raw = get_news_for_quarter(
        ticker, company_name,
        current_fq.start_date.isoformat(),
        current_fq.end_date.isoformat(),
    )
    prior_news_raw = get_news_for_quarter(
        ticker, company_name,
        prior_fq.start_date.isoformat(),
        prior_fq.end_date.isoformat(),
    )

    logger.info(
        f"news_tiering [{ticker}]: current={len(current_news_raw)} items, prior={len(prior_news_raw)} items"
    )

    # 2. Format for LLM
    def format_news_list(news_items: list[dict]) -> str:
        if not news_items:
            return "No news items found."
        return "\n".join(
            f"- [{item.get('published_date', 'unknown')}] {item.get('headline', '')}"
            for item in news_items[:30]  # cap at 30 items to control tokens
        )

    user_msg = NEWS_TIERING_USER.format(
        company_name=company_name,
        ticker=ticker,
        current_quarter=current_fq.label,
        prior_quarter=prior_fq.label,
        current_news=format_news_list(current_news_raw),
        prior_news=format_news_list(prior_news_raw),
    )

    # 3. Call LLM
    client = get_llm_client()
    try:
        raw_response = client.complete(
            system_prompt=NEWS_TIERING_SYSTEM,
            user_message=user_msg,
            operation_name=f"news_tiering_{ticker}",
        )
        logger.debug(f"news_tiering [{ticker}]: LLM response received")
        # Parse JSON from response
        # LLM may wrap in ```json ... ``` — strip that
        clean = raw_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
    except Exception as e:
        logger.warning(f"News tiering LLM failed for {ticker}: {e}")
        # Graceful fallback: classify all news as Tier 3
        result = {
            "classified_news": [
                {
                    "headline": n.get("headline", ""),
                    "tier": 3,
                    "reasoning": "fallback",
                    "date": n.get("published_date", ""),
                }
                for n in current_news_raw
            ],
            "current_quarter_raw_score": len(current_news_raw) * 3,
            "composition_shift": None,
            "composition_shift_reasoning": "LLM unavailable",
        }

    # 4. Split classified news back into current/prior
    classified = result.get("classified_news", [])

    # Map back to quarters by date
    current_quarter_news = []
    prior_quarter_news = []
    for item in classified:
        try:
            item_date = date.fromisoformat(item.get("date", "")[:10])
            if current_fq.start_date <= item_date <= current_fq.end_date:
                current_quarter_news.append(
                    {"tier": item["tier"], "headline": item["headline"], "date": item.get("date", "")}
                )
            elif prior_fq.start_date <= item_date <= prior_fq.end_date:
                prior_quarter_news.append(
                    {"tier": item["tier"], "headline": item["headline"], "date": item.get("date", "")}
                )
        except (ValueError, KeyError):
            # Can't parse date — put in current quarter
            current_quarter_news.append(
                {
                    "tier": item.get("tier", 3),
                    "headline": item.get("headline", ""),
                    "date": "",
                }
            )

    all_sources = list(
        set(
            sources
            + [n.get("url", "") for n in current_news_raw if n.get("url")]
            + ["yfinance_news", "google_news_rss"]
        )
    )

    return {
        "current_quarter_news": current_quarter_news,
        "prior_quarter_news": prior_quarter_news,
        "composition_shift": result.get("composition_shift"),
        "llm_reasoning": result.get("composition_shift_reasoning", ""),
        "sources": [s for s in all_sources if s],
    }
