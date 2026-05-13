from utils.logger import logger
from data.news_fetcher import get_company_news, get_news_for_quarter as _get_news_for_quarter


class YFinanceNewsProvider:
    provider_name = "yfinance"

    def get_news(self, ticker: str, company_name: str, days_back: int = 90) -> list[dict]:
        return get_company_news(ticker, company_name, days_back) or []

    def get_news_for_quarter(self, ticker: str, company_name: str, quarter_start: str, quarter_end: str) -> list[dict]:
        return _get_news_for_quarter(ticker, company_name, quarter_start, quarter_end) or []
