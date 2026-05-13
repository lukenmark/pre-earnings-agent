from datetime import datetime
from typing import Literal
from pydantic import BaseModel

WEIGHTS: dict[str, float] = {
    "sector_etf_fund_flows": 0.12,
    "vc_private_capital_inflow": 0.12,
    "analyst_revenue_estimates": 0.12,
    "sector_etf_3m_return": 0.08,
    "sector_relative_strength": 0.08,
    "breadth_of_participation": 0.08,
    "industry_earnings_growth": 0.08,
    "gdp_growth_rate": 0.05,
    "fed_funds_rate_direction": 0.05,
    "government_policy_spending": 0.05,
    "ism_pmi": 0.05,
    "industry_tam_growth": 0.05,
    "regulatory_environment": 0.04,
    "business_cycle_position": 0.03,
    "industry_earnings_growth_rate": 0.00,
}


class IndustryAssessment(BaseModel):
    id: int | None = None
    industry_name: str
    composite_score: int
    metrics: dict[str, float]
    status: Literal["active", "dropped"] = "active"
    consecutive_low_weeks: int = 0
    assessed_at: datetime
    notes: str | None = None

    def compute_composite(self) -> int:
        total = sum(WEIGHTS.get(k, 0.0) * v for k, v in self.metrics.items())
        return round(total)
