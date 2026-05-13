import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from data.cache import get, set, make_key
from utils.logger import logger


def _retry_decorator():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=False,
    )


@_retry_decorator()
def _fetch_history(ticker: str, period: str):
    return yf.Ticker(ticker).history(period=period)


@_retry_decorator()
def _fetch_info(ticker: str):
    return yf.Ticker(ticker).info


@_retry_decorator()
def _fetch_options_expiries(ticker: str):
    return yf.Ticker(ticker).options


@_retry_decorator()
def _fetch_option_chain(ticker: str, expiry: str):
    t = yf.Ticker(ticker)
    return t.option_chain(expiry)


def get_price_history(ticker: str, period: str = "6mo") -> dict | None:
    """Returns OHLCV as dict with keys: dates, opens, highs, lows, closes, volumes"""
    key = make_key("prices", ticker, period)
    cached = get(key)
    if cached is not None:
        return cached
    try:
        hist = _fetch_history(ticker, period)
        if hist is None or hist.empty:
            logger.warning(f"Empty price history for {ticker}")
            return None
        result = {
            "dates": [str(d.date()) for d in hist.index],
            "opens": hist["Open"].tolist(),
            "highs": hist["High"].tolist(),
            "lows": hist["Low"].tolist(),
            "closes": hist["Close"].tolist(),
            "volumes": hist["Volume"].tolist(),
        }
        set(key, result, "prices")
        return result
    except Exception as e:
        logger.warning(f"get_price_history({ticker}): {e}")
        return None


def get_quarterly_price_change(ticker: str, days: int = 90) -> float | None:
    """Returns % price change over last N days"""
    hist = get_price_history(ticker, "6mo")
    if not hist or len(hist["closes"]) < 2:
        return None
    try:
        closes = hist["closes"]
        # find index roughly `days` back
        idx = max(0, len(closes) - days)
        start_price = closes[idx]
        end_price = closes[-1]
        if start_price == 0:
            return None
        return (end_price - start_price) / start_price * 100
    except Exception as e:
        logger.warning(f"get_quarterly_price_change({ticker}): {e}")
        return None


def get_market_cap(ticker: str) -> float | None:
    """Returns market cap in dollars"""
    key = make_key("prices", ticker, "market_cap")
    cached = get(key)
    if cached is not None:
        return cached
    try:
        info = _fetch_info(ticker)
        if info is None:
            return None
        mc = info.get("marketCap")
        if mc:
            set(key, mc, "prices")
        return mc
    except Exception as e:
        logger.warning(f"get_market_cap({ticker}): {e}")
        return None


def get_options_chain(ticker: str) -> dict | None:
    """Returns nearest expiry options chain as dict"""
    key = make_key("options", ticker)
    cached = get(key)
    if cached is not None:
        return cached
    try:
        expiries = _fetch_options_expiries(ticker)
        if not expiries:
            logger.warning(f"No options expiries for {ticker}")
            return None
        nearest = expiries[0]
        chain = _fetch_option_chain(ticker, nearest)
        if chain is None:
            return None
        result = {
            "expiry": nearest,
            "calls": chain.calls.to_dict(orient="records"),
            "puts": chain.puts.to_dict(orient="records"),
        }
        set(key, result, "options")
        return result
    except Exception as e:
        logger.warning(f"get_options_chain({ticker}): {e}")
        return None


def get_stock_info(ticker: str) -> dict | None:
    """Returns yfinance info dict (eps, shares, float, etc.)"""
    key = make_key("prices", ticker, "info")
    cached = get(key)
    if cached is not None:
        return cached
    try:
        info = _fetch_info(ticker)
        if info is None:
            return None
        # serialize to plain dict (yfinance returns dict but may have non-serializable values)
        safe_info = {}
        for k, v in info.items():
            try:
                import json
                json.dumps(v)
                safe_info[k] = v
            except (TypeError, ValueError):
                safe_info[k] = str(v)
        set(key, safe_info, "prices")
        return safe_info
    except Exception as e:
        logger.warning(f"get_stock_info({ticker}): {e}")
        return None
