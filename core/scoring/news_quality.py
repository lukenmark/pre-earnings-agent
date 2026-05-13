from datetime import datetime, timezone

from models.scores import FactorScore

TIER_POINTS = {1: 15, 2: 8, 3: 3}

COMPOSITION_MODIFIERS = {
    "acquisitions_to_contracts": 10,
    "contracts_to_acquisitions": -5,
    None: 0,
}


def score_news_quality(
    current_quarter_news: list[dict],
    prior_quarter_news: list[dict],
    composition_shift: str | None,
    sources: list[str] = [],
) -> FactorScore:
    current_raw = sum(TIER_POINTS[item["tier"]] for item in current_quarter_news)
    prior_raw = sum(TIER_POINTS[item["tier"]] for item in prior_quarter_news)

    if prior_raw == 0:
        delta = 100.0 if current_raw > 0 else 0.0
        delta_pct = delta
    else:
        delta_pct = (current_raw - prior_raw) / prior_raw * 100

    if delta_pct > 50:
        score = 90 + min(10, (delta_pct - 50) / 5)
        bucket = ">+50%"
    elif delta_pct >= 20:
        score = 70 + (delta_pct - 20) / 30 * 20
        bucket = "+20% to +50%"
    elif delta_pct >= -20:
        score = 50 + delta_pct / 20 * 20
        bucket = "-20% to +20%"
    elif delta_pct >= -50:
        score = 30 + (delta_pct + 50) / 30 * 20
        bucket = "-50% to -20%"
    else:
        score = 10 + max(0, (delta_pct + 100) / 50 * 20)
        bucket = "<-50%"

    modifier = COMPOSITION_MODIFIERS.get(composition_shift, 0)
    score += modifier
    score = max(0, min(100, score))

    reasoning = (
        f"Current quarter raw: {current_raw} pts, prior quarter raw: {prior_raw} pts. "
        f"Delta: {delta_pct:.1f}% — bucket '{bucket}'. "
        f"Pre-modifier score: {score - modifier:.1f}. "
        f"Composition shift '{composition_shift}' applied modifier: {modifier:+d}. "
        f"Final score: {int(score)}."
    )

    return FactorScore(
        factor_name="news_quality",
        score=int(score),
        reasoning=reasoning,
        raw_inputs={
            "current_raw": current_raw,
            "prior_raw": prior_raw,
            "delta_pct": round(delta_pct, 2),
            "bucket": bucket,
            "composition_shift": composition_shift,
            "modifier": modifier,
        },
        sources=sources,
        scored_at=datetime.now(timezone.utc),
    )
