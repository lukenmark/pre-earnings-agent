from datetime import datetime, timezone

from models.scores import FactorScore

QOQ_MODIFIERS = {"positive": 10, "flat": 0, "negative": -10}
MARGIN_MODIFIERS = {"expanding": 5, "stable": 0, "compressing": -10}


def _yoy_base_score(yoy: float) -> float:
    if yoy >= 30:
        return 100.0
    elif yoy >= 20:
        return 80 + (yoy - 20) / 10 * 10
    elif yoy >= 10:
        return 60 + (yoy - 10) / 10 * 20
    elif yoy >= 5:
        return 40 + (yoy - 5) / 5 * 20
    elif yoy >= 0:
        return 20 + yoy / 5 * 20
    else:
        # negative: 0% → 20, -20%+ → 0
        return max(0.0, 20 + yoy / 20 * 20)


def score_revenue_trend(
    yoy_growth_pct: float,
    qoq_direction: str,
    gross_margin_trend: str,
    sources: list[str] = [],
) -> FactorScore:
    base = _yoy_base_score(yoy_growth_pct)
    qoq_mod = QOQ_MODIFIERS.get(qoq_direction, 0)
    margin_mod = MARGIN_MODIFIERS.get(gross_margin_trend, 0)

    score = max(0, min(100, int(base + qoq_mod + margin_mod)))

    reasoning = (
        f"YoY growth {yoy_growth_pct:.1f}% → base score {base:.1f}. "
        f"QoQ direction '{qoq_direction}': {qoq_mod:+d}. "
        f"Gross margin trend '{gross_margin_trend}': {margin_mod:+d}. "
        f"Final: {base:.1f} {qoq_mod:+d} {margin_mod:+d} = {score} (capped 0-100)."
    )

    return FactorScore(
        factor_name="revenue_trend",
        score=score,
        reasoning=reasoning,
        raw_inputs={
            "yoy_growth_pct": yoy_growth_pct,
            "qoq_direction": qoq_direction,
            "gross_margin_trend": gross_margin_trend,
            "base_score": round(base, 2),
            "qoq_modifier": qoq_mod,
            "margin_modifier": margin_mod,
        },
        sources=sources,
        scored_at=datetime.now(timezone.utc),
    )
