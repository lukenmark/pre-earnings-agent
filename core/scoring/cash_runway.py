from datetime import datetime, timezone

from models.scores import FactorScore


def score_cash_runway(
    cash_and_st_investments: float,
    quarterly_burn: float,
    sources: list[str] = [],
) -> FactorScore:
    if quarterly_burn <= 0:
        quarters = None
        score = 100
        reasoning = f"Cash flow positive (quarterly_burn={quarterly_burn}). Score=100."
    else:
        quarters = cash_and_st_investments / quarterly_burn
        if quarters >= 6:
            score = 100
        elif quarters >= 4:
            score = 70
        elif quarters >= 2:
            score = 40
        else:
            score = 10
        reasoning = (
            f"Cash=${cash_and_st_investments:,.0f}, burn=${quarterly_burn:,.0f}/qtr → "
            f"{quarters:.2f} quarters runway. Score={score}."
        )

    return FactorScore(
        factor_name="cash_runway",
        score=score,
        reasoning=reasoning,
        raw_inputs={
            "cash_and_st_investments": cash_and_st_investments,
            "quarterly_burn": quarterly_burn,
            "quarters_runway": quarters,
        },
        sources=sources,
        scored_at=datetime.now(timezone.utc),
    )
