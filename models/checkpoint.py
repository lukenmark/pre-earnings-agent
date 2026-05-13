from datetime import datetime
from typing import Literal
from pydantic import BaseModel, model_validator

from models.scores import FactorScore


class CheckpointReport(BaseModel):
    id: int | None = None
    ticker: str
    checkpoint: Literal["T-21", "T-14", "T-7", "T-3"]
    composite_score: int
    decision: Literal["BUY", "WATCH", "NO_GO"]
    hypothesis_direction: Literal["bullish", "neutral", "bearish"]
    hard_veto: bool = False
    core_override_triggered: bool = False
    factor_scores: dict[str, FactorScore]
    key_findings: list[str]
    flags: list[str]
    prior_composite_score: int | None = None
    score_delta: int | None = None
    includes_mbp: bool = False
    created_at: datetime

    @model_validator(mode="after")
    def compute_score_delta(self) -> "CheckpointReport":
        if self.prior_composite_score is not None:
            object.__setattr__(self, "score_delta", self.composite_score - self.prior_composite_score)
        return self
