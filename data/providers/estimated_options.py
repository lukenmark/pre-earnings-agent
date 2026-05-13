from utils.logger import logger
from data.options_fetcher import get_options_metrics


class EstimatedOptionsProvider:
    provider_name = "estimated_yfinance"
    data_quality = "estimated"

    def get_metrics(self, ticker: str) -> dict | None:
        return get_options_metrics(ticker)
