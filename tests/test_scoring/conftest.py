import pytest
from datetime import datetime, timezone

from models.scores import FactorScore


def _fs(name: str, score: int = 75) -> FactorScore:
    return FactorScore(
        factor_name=name,
        score=score,
        reasoning="test fixture",
        raw_inputs={"hard_veto": False},
        sources=[],
        scored_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def neutral_factor_scores() -> dict[str, FactorScore]:
    return {
        "news_quality": _fs("news_quality"),
        "price_absorption_gap": _fs("price_absorption_gap"),
        "industry_momentum": _fs("industry_momentum"),
        "revenue_trend": _fs("revenue_trend"),
        "earnings_profile": _fs("earnings_profile"),
        "options_flow": _fs("options_flow"),
        "insider_activity": _fs("insider_activity"),
        "cash_runway": _fs("cash_runway"),
    }
