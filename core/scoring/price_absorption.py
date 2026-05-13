from datetime import datetime, timezone

from models.scores import FactorScore

SUPPRESSION_MULTIPLIERS = {
    "mechanical": 1.2,
    "none_identified": 1.4,
    "fundamental": 0.5,
    "not_suppressed": 1.0,
}


def _compute_c1(news_quality_score: int, quarterly_price_change_pct: float) -> float:
    chg = quarterly_price_change_pct
    if news_quality_score >= 60:
        if chg <= 0:
            # 0% → 80, -20%+ → 100, clamp
            c1 = 80 + min(20, (-chg) / 20 * 20)
            return max(80.0, min(100.0, c1))
        elif chg <= 50:
            # 0% → 60, +50% → 40
            c1 = 60 - (chg / 50) * 20
            return max(40.0, min(60.0, c1))
        else:
            # +50% → 30, +100% → 0, floor 0
            c1 = 30 - ((chg - 50) / 50) * 30
            return max(0.0, min(30.0, c1))
    else:
        return 50.0


def _compute_c3(quarterly_price_change_pct: float) -> float:
    chg = quarterly_price_change_pct
    if chg <= 0:
        # 0% → 90, -20%+ → 100
        c3 = 90 + min(10, (-chg) / 20 * 10)
        return max(90.0, min(100.0, c3))
    elif chg <= 30:
        # +1% → 70, +30% → 50  (linear)
        c3 = 70 - ((chg - 1) / 29) * 20 if chg >= 1 else 70.0
        return max(50.0, min(70.0, c3))
    elif chg <= 50:
        # +30% → 50, +50% → 20
        c3 = 50 - ((chg - 30) / 20) * 30
        return max(20.0, min(50.0, c3))
    else:
        # +50% → 20, +100%+ → 0, floor 0
        c3 = 20 - ((chg - 50) / 50) * 20
        return max(0.0, min(20.0, c3))


def score_price_absorption(
    quarterly_price_change_pct: float,
    news_quality_score: int,
    suppression_cause: str,
    sources: list[str] = [],
) -> FactorScore:
    c1 = _compute_c1(news_quality_score, quarterly_price_change_pct)

    multiplier = SUPPRESSION_MULTIPLIERS.get(suppression_cause, 1.0)
    c2_adjusted = c1 * multiplier

    c3 = _compute_c3(quarterly_price_change_pct)

    final = (c1 * 0.50) + (c2_adjusted * 0.30) + (c3 * 0.20)
    final = max(0.0, min(100.0, final))

    if news_quality_score >= 60:
        c1_basis = f"strong news (score={news_quality_score}), price change={quarterly_price_change_pct:+.1f}%"
    else:
        c1_basis = f"weak/neutral news (score={news_quality_score}), tracking baseline=50"

    reasoning = (
        f"C1={c1:.1f} ({c1_basis}). "
        f"Suppression cause='{suppression_cause}', multiplier={multiplier:.1f} → C2_adjusted={c2_adjusted:.1f}. "
        f"C3={c3:.1f} (catalyst remaining, price chg={quarterly_price_change_pct:+.1f}%). "
        f"Final = ({c1:.1f}*0.50) + ({c2_adjusted:.1f}*0.30) + ({c3:.1f}*0.20) = {final:.1f}."
    )

    return FactorScore(
        factor_name="price_absorption_gap",
        score=int(final),
        reasoning=reasoning,
        raw_inputs={
            "quarterly_price_change_pct": quarterly_price_change_pct,
            "news_quality_score": news_quality_score,
            "suppression_cause": suppression_cause,
            "c1": round(c1, 2),
            "multiplier": multiplier,
            "c2_adjusted": round(c2_adjusted, 2),
            "c3": round(c3, 2),
        },
        sources=sources,
        scored_at=datetime.now(timezone.utc),
    )
