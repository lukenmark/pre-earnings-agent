import yfinance as yf
from data.cache import get, set, make_key
from data.yfinance_client import get_price_history
from utils.logger import logger

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Consumer Staples": "XLP",
    "Cybersecurity": "CIBR",
    "AI/Cloud": "CLOU",
    "Biotech": "IBB",
    "Defense": "ITA",
}


def _fuzzy_match_sector(sector_name: str) -> str | None:
    """Match a sector name to the ETF map, case-insensitive partial match."""
    sector_lower = sector_name.lower()
    for key, etf in SECTOR_ETF_MAP.items():
        if key.lower() in sector_lower or sector_lower in key.lower():
            return etf
    return None


def _compute_return(history: dict) -> float | None:
    """Returns % return from first to last close in a price history dict."""
    closes = history.get("closes", [])
    if not closes or len(closes) < 2:
        return None
    start = closes[0]
    end = closes[-1]
    if start == 0:
        return None
    return (end - start) / start * 100


def get_sector_etf_return(sector: str, months: int = 3) -> float | None:
    """Returns % return for sector ETF over N months relative to SPY"""
    etf = _fuzzy_match_sector(sector)
    if not etf:
        logger.warning(f"get_sector_etf_return: no ETF mapped for '{sector}'")
        return None

    key = make_key("industry", sector, months, "etf_return")
    cached = get(key)
    if cached is not None:
        return cached

    period = "3mo" if months <= 3 else "6mo" if months <= 6 else "1y"
    try:
        etf_hist = get_price_history(etf, period)
        spy_hist = get_price_history("SPY", period)
        if not etf_hist or not spy_hist:
            return None
        etf_return = _compute_return(etf_hist)
        spy_return = _compute_return(spy_hist)
        if etf_return is None or spy_return is None:
            return None
        relative = etf_return - spy_return
        set(key, relative, "industry")
        return relative
    except Exception as e:
        logger.warning(f"get_sector_etf_return({sector}): {e}")
        return None


def get_sector_breadth(sector_etf: str) -> float | None:
    """Returns approximation: % of last 50 trading days the ETF was above its 50-day MA."""
    key = make_key("industry", sector_etf, "breadth")
    cached = get(key)
    if cached is not None:
        return cached
    try:
        hist = get_price_history(sector_etf, "6mo")
        if not hist or len(hist["closes"]) < 50:
            return None
        closes = hist["closes"]
        # Rolling 50-day MA
        above_count = 0
        total = 0
        for i in range(50, len(closes)):
            ma50 = sum(closes[i - 50:i]) / 50
            if closes[i] > ma50:
                above_count += 1
            total += 1
        if total == 0:
            return None
        pct = above_count / total * 100
        set(key, pct, "industry")
        return pct
    except Exception as e:
        logger.warning(f"get_sector_breadth({sector_etf}): {e}")
        return None


def _score_relative_return(rel_return: float | None) -> float:
    """Convert relative ETF return to 0-100 score."""
    if rel_return is None:
        return 50.0
    # ±10% mapped to 0-100 with 50 at 0
    clamped = max(-10, min(10, rel_return))
    return 50.0 + (clamped / 10.0) * 50.0


def _score_breadth(breadth: float | None) -> float:
    """Breadth % directly maps to 0-100 score."""
    if breadth is None:
        return 50.0
    return max(0.0, min(100.0, breadth))


def _get_3mo_treasury_trend() -> float:
    """Derive fed funds rate direction from 3-month treasury trend."""
    try:
        hist = get_price_history("^IRX", "3mo")
        if not hist or len(hist["closes"]) < 10:
            return 50.0
        closes = hist["closes"]
        recent_avg = sum(closes[-10:]) / 10
        older_avg = sum(closes[:10]) / 10
        diff = recent_avg - older_avg
        # Rising rates = bearish (below 50), falling rates = bullish (above 50)
        clamped = max(-1.0, min(1.0, diff))
        return 50.0 - (clamped / 1.0) * 30.0
    except Exception as e:
        logger.warning(f"_get_3mo_treasury_trend: {e}")
        return 50.0


def get_industry_metrics(industry_name: str) -> dict:
    """
    Returns dict of metric_name → float (0-100) for all 15 metrics.
    Unavailable metrics return 50.0 (neutral).
    """
    key = make_key("industry", industry_name, "metrics")
    cached = get(key)
    if cached is not None:
        return cached

    etf = _fuzzy_match_sector(industry_name)

    # Compute what we can from free data
    etf_3m_return = get_sector_etf_return(industry_name, months=3)
    etf_6m_return = get_sector_etf_return(industry_name, months=6)
    breadth = get_sector_breadth(etf) if etf else None
    fed_score = _get_3mo_treasury_trend()

    sector_rs_score = _score_relative_return(etf_3m_return)
    etf_3m_score = _score_relative_return(etf_6m_return)
    breadth_score = _score_breadth(breadth)

    metrics = {
        # Derivable from free data
        "sector_etf_3m_return": round(etf_3m_score, 1),
        "sector_relative_strength": round(sector_rs_score, 1),
        "breadth_of_participation": round(breadth_score, 1),
        "fed_funds_rate_direction": round(fed_score, 1),

        # Estimated/static defaults — logged as unavailable
        "sector_etf_fund_flows": 50.0,       # requires paid flow data
        "vc_private_capital_inflow": 50.0,   # requires paid data
        "analyst_revenue_estimates": 50.0,   # requires paid data
        "gdp_growth_rate": 65.0,             # static: ~2.5% GDP growth → above neutral
        "government_policy_spending": 50.0,  # manual input required
        "ism_pmi": 60.0,                     # PMI ~52 → slightly above neutral
        "industry_tam_growth": 50.0,         # manual/LLM research required
        "regulatory_environment": 50.0,      # manual/LLM research required
        "business_cycle_position": 50.0,     # derived from macro, default neutral
        "industry_earnings_growth": 50.0,    # requires earnings data aggregation
        "industry_earnings_growth_rate": 50.0,
    }

    unavailable = [
        "sector_etf_fund_flows", "vc_private_capital_inflow",
        "analyst_revenue_estimates", "government_policy_spending",
        "industry_tam_growth", "regulatory_environment",
        "industry_earnings_growth",
    ]
    logger.debug(
        f"get_industry_metrics({industry_name}): {len(unavailable)} metrics set to neutral (paid data unavailable)"
    )

    set(key, metrics, "industry")
    return metrics
