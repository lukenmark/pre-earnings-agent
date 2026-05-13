from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class FinalAlert(BaseModel):
    id: int | None = None
    ticker: str
    company_name: str
    recommendation: Literal["BUY", "NO_GO"]
    composite_score: int
    checkpoint_trajectory: list[int]
    core_news_score: int
    core_pag_score: int
    insider_summary: str
    options_snapshot: str
    share_structure_summary: str
    thesis: str
    earnings_date: datetime
    alert_sent_at: datetime
    hard_veto: bool = False
