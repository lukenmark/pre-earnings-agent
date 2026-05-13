from datetime import datetime, timezone

from models.scores import FactorScore


def score_industry_momentum(
    industry_composite_score: int,
    industry_name: str,
    sources: list[str] = [],
) -> FactorScore:
    score = max(0, min(100, industry_composite_score))

    reasoning = (
        f"Industry '{industry_name}' — direct pass-through of weekly IndustryAssessment "
        f"composite score: {industry_composite_score}."
    )

    return FactorScore(
        factor_name="industry_momentum",
        score=score,
        reasoning=reasoning,
        raw_inputs={
            "industry_composite_score": industry_composite_score,
            "industry_name": industry_name,
        },
        sources=sources,
        scored_at=datetime.now(timezone.utc),
    )
