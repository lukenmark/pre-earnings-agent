from datetime import datetime, timezone

from models.scores import FactorScore


def score_insider_activity(
    open_market_buys_detected: bool,
    heavy_discretionary_selling: bool,
    small_discretionary_selling: bool,
    sources: list[str] = [],
) -> FactorScore:
    if heavy_discretionary_selling:
        return FactorScore(
            factor_name="insider_activity",
            score=0,
            reasoning="HARD_VETO_TRIGGERED: Heavy discretionary insider selling detected. Score forced to 0.",
            raw_inputs={
                "open_market_buys_detected": open_market_buys_detected,
                "heavy_discretionary_selling": heavy_discretionary_selling,
                "small_discretionary_selling": small_discretionary_selling,
                "hard_veto": True,
            },
            sources=sources,
            scored_at=datetime.now(timezone.utc),
        )

    if open_market_buys_detected:
        score = 100
        reasoning = "Open market buys detected. Score=100 (bullish signal)."
    elif small_discretionary_selling:
        score = 30
        reasoning = "Small discretionary selling detected (no buys). Score=30."
    else:
        score = 60
        reasoning = "No significant insider activity detected. Score=60 (neutral)."

    return FactorScore(
        factor_name="insider_activity",
        score=score,
        reasoning=reasoning,
        raw_inputs={
            "open_market_buys_detected": open_market_buys_detected,
            "heavy_discretionary_selling": heavy_discretionary_selling,
            "small_discretionary_selling": small_discretionary_selling,
            "hard_veto": False,
        },
        sources=sources,
        scored_at=datetime.now(timezone.utc),
    )
