import os
from dotenv import load_dotenv

from utils.logger import logger

load_dotenv()


def get_news_provider():
    """Returns configured NewsProvider based on NEWS_PROVIDER env var"""
    provider = os.getenv("NEWS_PROVIDER", "yfinance").lower()
    if provider == "yfinance":
        from data.providers.yfinance_news import YFinanceNewsProvider
        return YFinanceNewsProvider()
    # Future: "benzinga", "newsapi", etc.
    from data.providers.yfinance_news import YFinanceNewsProvider
    return YFinanceNewsProvider()


def get_options_provider():
    """Returns configured OptionsFlowProvider"""
    provider = os.getenv("OPTIONS_PROVIDER", "estimated").lower()
    if provider in ("estimated", "yfinance"):
        from data.providers.estimated_options import EstimatedOptionsProvider
        return EstimatedOptionsProvider()
    # Future: "unusual_whales", "market_chameleon", etc.
    from data.providers.estimated_options import EstimatedOptionsProvider
    return EstimatedOptionsProvider()


def get_industry_provider():
    """Returns configured IndustryDataProvider"""
    provider = os.getenv("INDUSTRY_PROVIDER", "yfinance").lower()
    if provider == "yfinance":
        from data.providers.yfinance_industry import YFinanceIndustryProvider
        return YFinanceIndustryProvider()
    from data.providers.yfinance_industry import YFinanceIndustryProvider
    return YFinanceIndustryProvider()
