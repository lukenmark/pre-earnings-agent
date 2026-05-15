from data.cache import get, set, make_key
from utils.logger import logger

try:
    from finvizfinance.screener.overview import Overview as FinvizOverview
    _FINVIZ_AVAILABLE = True
except ImportError:
    _FINVIZ_AVAILABLE = False
    logger.warning("finvizfinance not available — screener will use fallback mock data")


MOCK_CANDIDATES = [
    {"ticker": "NVDA", "company": "NVIDIA Corp", "market_cap": 2_800_000_000_000, "eps_ttm": 2.42, "debt_equity": 0.41, "inst_own_pct": 65.0, "sales_growth": 122.0, "pe_ratio": 45.0},
    {"ticker": "SMCI", "company": "Super Micro Computer", "market_cap": 25_000_000_000, "eps_ttm": 1.82, "debt_equity": 0.62, "inst_own_pct": 55.0, "sales_growth": 37.0, "pe_ratio": 28.0},
    {"ticker": "CELH", "company": "Celsius Holdings", "market_cap": 4_500_000_000, "eps_ttm": 0.82, "debt_equity": 0.05, "inst_own_pct": 48.0, "sales_growth": 28.0, "pe_ratio": 35.0},
]


def _parse_finviz_value(value: str | None, is_pct: bool = False) -> float | None:
    if value is None or value == "-":
        return None
    try:
        v = str(value).replace(",", "").replace("%", "").strip()
        if v.endswith("B"):
            return float(v[:-1]) * 1_000_000_000
        if v.endswith("M"):
            return float(v[:-1]) * 1_000_000
        if v.endswith("K"):
            return float(v[:-1]) * 1_000
        return float(v)
    except (ValueError, AttributeError):
        return None


def run_finviz_screen() -> list[dict]:
    """
    Screens for profitable US growth stocks reporting this calendar month.
    "This Month" keeps the watchlist relevant — only stocks with imminent earnings.

    Finviz filters:
    - Earnings Date: This Month  — reporting this calendar month
    - USA only
    - 5-year sales growth > 15% — proven revenue growers
    - P/E: Profitable (>0)       — eliminates money-losers up front

    market cap / debt / inst_own filtering happens in apply_penalty_scoring()
    using real yfinance data. Cached 1 hour.
    """
    key = make_key("finviz", "screen")
    cached = get(key)
    if cached is not None:
        logger.info(f"finviz_screener: cached results ({len(cached)} candidates)")
        return cached

    if not _FINVIZ_AVAILABLE:
        logger.warning("finviz_screener: using mock fallback — install finvizfinance")
        return MOCK_CANDIDATES

    try:
        foverview = FinvizOverview()
        foverview.set_filter(filters_dict={
            "Earnings Date": "This Month",
            "Country": "USA",
            "Sales growthpast 5 years": "Over 15%",
            "P/E": "Profitable (>0)",
        })
        df = foverview.screener_view()
        if df is None or df.empty:
            logger.info("finviz_screener: no results this month — normal between earnings seasons")
            set(key, [], "finviz")
            return []

        candidates = []
        for _, row in df.iterrows():
            d = row.to_dict()
            candidates.append({
                "ticker": d.get("Ticker", ""),
                "company": d.get("Company", ""),
                "market_cap": _parse_finviz_value(d.get("Market Cap")),
                "eps_ttm": _parse_finviz_value(d.get("EPS (ttm)")),
                "debt_equity": _parse_finviz_value(d.get("Debt/Eq")),
                "inst_own_pct": _parse_finviz_value(d.get("Inst Own"), is_pct=True),
                "sales_growth": _parse_finviz_value(d.get("Sales past 5Y"), is_pct=True),
                "pe_ratio": _parse_finviz_value(d.get("P/E")),
                "sector": d.get("Sector", ""),
                "industry": d.get("Industry", ""),
            })

        logger.info(f"finviz_screener: {len(candidates)} candidates reporting this month")
        set(key, candidates, "finviz")
        return candidates

    except Exception as e:
        logger.warning(f"run_finviz_screen: {e} — using mock fallback")
        return MOCK_CANDIDATES


def apply_penalty_scoring(candidates: list[dict]) -> list[dict]:
    """
    Applies soft cap penalty zones. Adds 'screen_score' (0-100) and 'excluded' flag.

    Penalty rules:
    - Market cap $300M-$15B: 0 penalty. $15B-$20B: graduated -5 to -15. Outside: exclude.
    - EPS: positive or 0 to -0.15: 0 penalty. -0.15 to -0.50: graduated -5 to -20. < -0.50: exclude.
    - Debt/Equity: < 1.0: 0 penalty. 1.0-1.5: graduated -5 to -15. > 1.5: exclude.
    - Inst ownership: < 65%: 0 penalty. 65-90%: graduated -5 to -15. > 90%: exclude.
    """
    results = []
    for c in candidates:
        score = 100
        excluded = False
        exclusion_reason = []

        mc = c.get("market_cap")
        if mc is not None:
            if mc < 300_000_000 or mc > 20_000_000_000:
                excluded = True
                exclusion_reason.append(f"market_cap outside 300M-20B")
            elif mc > 15_000_000_000:
                penalty = int((mc - 15_000_000_000) / 1_000_000_000)
                score -= min(15, penalty)

        eps = c.get("eps_ttm")
        if eps is not None and eps < 0:
            if eps < -0.50:
                excluded = True
                exclusion_reason.append(f"eps_ttm={eps:.2f} < -0.50")
            elif eps < -0.15:
                penalty = int(abs(eps + 0.15) / 0.35 * 20)
                score -= min(20, max(5, penalty))

        de = c.get("debt_equity")
        if de is not None:
            if de > 1.5:
                excluded = True
                exclusion_reason.append(f"debt_equity={de:.2f} > 1.5")
            elif de > 1.0:
                penalty = int((de - 1.0) / 0.5 * 15)
                score -= min(15, max(5, penalty))

        inst = c.get("inst_own_pct")
        if inst is not None:
            if inst > 90.0:
                excluded = True
                exclusion_reason.append(f"inst_own={inst:.1f}% > 90%")
            elif inst > 65.0:
                penalty = int((inst - 65.0) / 25.0 * 15)
                score -= min(15, max(5, penalty))

        result = {**c, "screen_score": max(0, score), "excluded": excluded}
        if exclusion_reason:
            result["exclusion_reason"] = "; ".join(exclusion_reason)
        results.append(result)
    return results


def screen_candidates(industry_filter: list[str] | None = None) -> list[dict]:
    """
    Full pipeline: Finviz screen → penalty scoring → filter excludes → sort.
    Returns ALL passing candidates (no cap — watchlist_manager decides how many to add).
    """
    raw = run_finviz_screen()
    scored = apply_penalty_scoring(raw)
    active = [c for c in scored if not c.get("excluded", False)]

    if industry_filter:
        filter_lower = [f.lower() for f in industry_filter]
        for c in active:
            industry = (c.get("industry") or c.get("sector") or "").lower()
            c["_priority"] = any(f in industry for f in filter_lower)
        active.sort(key=lambda c: (not c.get("_priority", False), -c["screen_score"]))
    else:
        active.sort(key=lambda c: -c["screen_score"])

    return active
