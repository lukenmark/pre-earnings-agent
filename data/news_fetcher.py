from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

import requests
import yfinance as yf
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

import data.cache as _cache
from utils.logger import logger

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def _fetch_google_rss(query: str) -> list[dict]:
    url = f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    # Parse RSS — use xml parser; fall back to lxml then html.parser
    for parser in ("xml", "lxml-xml", "lxml", "html.parser"):
        try:
            soup = BeautifulSoup(resp.text, parser)
            if soup.find("item"):
                break
        except Exception:
            continue
    else:
        return []
    items = []
    for item in soup.find_all("item"):
        pub_str = item.findtext("pubDate", "")
        try:
            pub_dt = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %Z")
            pub_iso = pub_dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pub_iso = pub_str
        items.append(
            {
                "headline": item.findtext("title", "").strip(),
                "source": item.findtext("source", "Google News"),
                "published_date": pub_iso,
                "url": item.findtext("link", ""),
                "summary": item.findtext("description", None),
            }
        )
    return items


def _fetch_yfinance_news(ticker: str) -> list[dict]:
    try:
        raw = yf.Ticker(ticker).news or []
        results = []
        for item in raw:
            pub_ts = item.get("providerPublishTime") or item.get("publishedAt")
            if pub_ts:
                try:
                    pub_iso = datetime.utcfromtimestamp(int(pub_ts)).strftime("%Y-%m-%dT%H:%M:%S")
                except (ValueError, TypeError):
                    pub_iso = str(pub_ts)
            else:
                pub_iso = ""

            # yfinance 0.2+ nests content differently
            content = item.get("content", {})
            if isinstance(content, dict):
                headline = content.get("title", item.get("title", ""))
                url = content.get("canonicalUrl", {})
                if isinstance(url, dict):
                    url = url.get("url", item.get("link", ""))
                provider = content.get("provider", {})
                if isinstance(provider, dict):
                    source = provider.get("displayName", "Yahoo Finance")
                else:
                    source = "Yahoo Finance"
                summary = content.get("summary", None)
            else:
                headline = item.get("title", "")
                url = item.get("link", "")
                source = "Yahoo Finance"
                summary = None

            results.append(
                {
                    "headline": headline.strip(),
                    "source": source,
                    "published_date": pub_iso,
                    "url": url if isinstance(url, str) else "",
                    "summary": summary,
                }
            )
        return results
    except Exception as e:
        logger.warning(f"_fetch_yfinance_news({ticker}): {e}")
        return []


def _deduplicate(news: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in news:
        key = item["headline"][:60].lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _filter_by_days(news: list[dict], days_back: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    results = []
    for item in news:
        pub = item.get("published_date", "")
        if not pub:
            results.append(item)
            continue
        try:
            pub_dt = datetime.fromisoformat(pub)
            if pub_dt >= cutoff:
                results.append(item)
        except ValueError:
            results.append(item)
    return results


def get_company_news(
    ticker: str,
    company_name: str,
    days_back: int = 90,
) -> list[dict]:
    """Returns deduplicated news sorted by date descending"""
    key = _cache.make_key("news", ticker, days_back)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    all_news = []

    # Source 1: yfinance
    yf_news = _fetch_yfinance_news(ticker)
    all_news.extend(yf_news)
    logger.debug(f"news: {len(yf_news)} items from yfinance for {ticker}")

    # Source 2: Google News RSS
    try:
        google_news = _fetch_google_rss(f"{ticker} {company_name} earnings") or []
        all_news.extend(google_news)
        logger.debug(f"news: {len(google_news)} items from Google News for {ticker}")
    except Exception as e:
        logger.warning(f"Google News RSS failed for {ticker}: {e}")

    filtered = _filter_by_days(all_news, days_back)
    deduped = _deduplicate(filtered)
    # Sort by date descending
    def sort_key(item):
        pub = item.get("published_date", "")
        return pub or ""
    deduped.sort(key=sort_key, reverse=True)

    _cache.set(key, deduped, "news")
    return deduped


def filter_news_by_date_range(
    news: list[dict],
    start_date: str,
    end_date: str,
) -> list[dict]:
    """Filter news list to a specific date range"""
    results = []
    for item in news:
        pub = item.get("published_date", "")
        if not pub:
            continue
        try:
            pub_dt = datetime.fromisoformat(pub)
            if start_date <= pub_dt.strftime("%Y-%m-%d") <= end_date:
                results.append(item)
        except ValueError:
            continue
    return results


def get_news_for_quarter(
    ticker: str,
    company_name: str,
    quarter_start: str,
    quarter_end: str,
) -> list[dict]:
    """Get news within a specific fiscal quarter"""
    start_dt = datetime.fromisoformat(quarter_start)
    days_back = (datetime.now(timezone.utc) - start_dt).days + 5
    days_back = max(days_back, 1)
    all_news = get_company_news(ticker, company_name, days_back=days_back)
    return filter_news_by_date_range(all_news, quarter_start, quarter_end)
