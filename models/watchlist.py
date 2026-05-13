from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel


class WatchlistEntry(BaseModel):
    ticker: str
    company_name: str
    earnings_date: date | None = None
    fiscal_year_end: str | None = None
    status: Literal["candidate", "active", "buy_alert", "no_go", "completed"] = "candidate"
    date_added: datetime
    industry: str | None = None
    eps_ttm: float | None = None
    market_cap: float | None = None
    notes: str | None = None
