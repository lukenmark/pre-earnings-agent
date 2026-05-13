from datetime import datetime
from pydantic import BaseModel


class FactorScore(BaseModel):
    factor_name: str
    score: int
    reasoning: str
    raw_inputs: dict
    sources: list[str]
    scored_at: datetime
