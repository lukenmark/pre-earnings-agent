from data.cache import get, set, make_key
from data.yfinance_client import get_options_chain, get_price_history
from utils.logger import logger


def get_options_metrics(ticker: str) -> dict | None:
    """
    Returns options flow metrics derived from yfinance.

    NOTE on data quality:
    - call_sizzle_index / put_sizzle_index: True sizzle requires historical options volume (paid).
      We return today's total volume for the nearest expiry only; set data_quality="estimated".
    - iv_percentile: approximated from ATM implied volatility vs 52-week price range.
    - volume_at_ask_pct / volume_at_bid_pct: not derivable from yfinance snapshot; set to 0.5/0.5.
    - bid_ask_spread_pct: computed from ATM call options.
    """
    key = make_key("options", ticker, "metrics")
    cached = get(key)
    if cached is not None:
        return cached

    try:
        chain_data = get_options_chain(ticker)
        if not chain_data:
            logger.warning(f"get_options_metrics({ticker}): no options chain data")
            return None

        calls = chain_data.get("calls", [])
        puts = chain_data.get("puts", [])

        if not calls and not puts:
            return None

        def _safe_vol(v) -> int:
            """Return 0 for None or NaN values."""
            try:
                import math
                if v is None or math.isnan(float(v)):
                    return 0
                return int(float(v))
            except (TypeError, ValueError):
                return 0

        # Total volumes
        total_call_vol = sum(_safe_vol(c.get("volume")) for c in calls)
        total_put_vol = sum(_safe_vol(p.get("volume")) for p in puts)

        call_put_ratio = (
            total_call_vol / total_put_vol if total_put_vol > 0 else float(total_call_vol)
        )

        # ATM option (closest strike to current price)
        hist = get_price_history(ticker, "5d")
        current_price = hist["closes"][-1] if hist and hist.get("closes") else None

        atm_iv = None
        bid_ask_spread_pct = 0.0
        if current_price and calls:
            atm_call = min(calls, key=lambda c: abs((c.get("strike") or 0) - current_price))
            bid = atm_call.get("bid") or 0
            ask = atm_call.get("ask") or 0
            mid = (bid + ask) / 2
            if mid > 0:
                bid_ask_spread_pct = (ask - bid) / mid * 100
            atm_iv = atm_call.get("impliedVolatility")

        # IV percentile approximation: compare current ATM IV vs 52-week price range
        # True IV percentile requires historical IV data (paid). We approximate using
        # the ratio of current IV to a rough historical baseline.
        iv_percentile = 50.0  # neutral default
        if atm_iv is not None:
            # Rough heuristic: IV of 0.3 = ~50th percentile, scale linearly
            iv_percentile = min(100.0, max(0.0, (atm_iv / 0.6) * 100))

        # Sizzle: without historical options volume, we can't compute properly
        # Return 1.0 (neutral) — "today's vol / avg = unknown"
        call_sizzle = 1.0
        put_sizzle = 1.0

        result = {
            "call_sizzle_index": call_sizzle,
            "put_sizzle_index": put_sizzle,
            "call_put_ratio": round(call_put_ratio, 3),
            "iv_percentile": round(iv_percentile, 1),
            "volume_at_ask_pct": 0.5,   # not derivable from snapshot data
            "volume_at_bid_pct": 0.5,   # not derivable from snapshot data
            "bid_ask_spread_pct": round(bid_ask_spread_pct, 2),
            "total_call_volume": int(total_call_vol),
            "total_put_volume": int(total_put_vol),
            "data_quality": "estimated",
        }

        set(key, result, "options")
        return result
    except Exception as e:
        logger.warning(f"get_options_metrics({ticker}): {e}")
        return None
