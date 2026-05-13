from typing import Protocol, runtime_checkable
from datetime import date

from utils.logger import logger


@runtime_checkable
class NewsProvider(Protocol):
    def get_news(self, ticker: str, company_name: str, days_back: int) -> list[dict]:
        """Returns list of {headline, source, published_date, url, summary}"""
        ...

    def get_news_for_quarter(self, ticker: str, company_name: str, quarter_start: str, quarter_end: str) -> list[dict]:
        ...

    @property
    def provider_name(self) -> str:
        ...


@runtime_checkable
class OptionsFlowProvider(Protocol):
    def get_metrics(self, ticker: str) -> dict | None:
        """Returns options flow metrics dict or None"""
        ...

    @property
    def provider_name(self) -> str:
        ...

    @property
    def data_quality(self) -> str:
        """'full' | 'estimated' | 'unavailable'"""
        ...


@runtime_checkable
class IndustryDataProvider(Protocol):
    def get_metrics(self, industry_name: str) -> dict:
        """Returns dict of metric_name → float (0-100) for all 15 metrics"""
        ...

    @property
    def provider_name(self) -> str:
        ...
