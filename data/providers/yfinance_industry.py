from utils.logger import logger
from data.industry_fetcher import get_industry_metrics


class YFinanceIndustryProvider:
    provider_name = "yfinance"

    def get_metrics(self, industry_name: str) -> dict:
        return get_industry_metrics(industry_name) or {}
