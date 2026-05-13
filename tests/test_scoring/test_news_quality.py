import pytest
from core.scoring.news_quality import score_news_quality, TIER_POINTS


def _news(tier: int, n: int = 1) -> list[dict]:
    return [{"tier": tier, "headline": "test", "date": "2024-01-01"}] * n


def test_tier_points_calculation():
    assert TIER_POINTS[1] == 15
    assert TIER_POINTS[2] == 8
    assert TIER_POINTS[3] == 3


def test_strong_improvement_above_50pct():
    # prior=15 (1xT1), current=60 (4xT1) → delta=+300%
    result = score_news_quality(
        current_quarter_news=_news(1, 4),
        prior_quarter_news=_news(1, 1),
        composition_shift=None,
    )
    assert 90 <= result.score <= 100


def test_flat_qoq():
    # same news both quarters → delta=0%
    result = score_news_quality(
        current_quarter_news=_news(1, 2),
        prior_quarter_news=_news(1, 2),
        composition_shift=None,
    )
    assert 50 <= result.score <= 70


def test_decline_below_50pct():
    # prior=60pts, current=8pts → delta = (8-60)/60*100 = -86.7%
    result = score_news_quality(
        current_quarter_news=_news(2, 1),
        prior_quarter_news=_news(1, 4),
        composition_shift=None,
    )
    assert 10 <= result.score <= 30


def test_zero_prior_quarter():
    # prior=0, current>0 → delta treated as 100%
    result = score_news_quality(
        current_quarter_news=_news(1, 1),
        prior_quarter_news=[],
        composition_shift=None,
    )
    assert result.score >= 90


def test_composition_shift_acquisitions_to_contracts():
    # flat delta (score~50), then +10 modifier
    result = score_news_quality(
        current_quarter_news=_news(1, 2),
        prior_quarter_news=_news(1, 2),
        composition_shift="acquisitions_to_contracts",
    )
    baseline = score_news_quality(
        current_quarter_news=_news(1, 2),
        prior_quarter_news=_news(1, 2),
        composition_shift=None,
    )
    assert result.score == min(100, baseline.score + 10)


def test_composition_shift_contracts_to_acquisitions():
    result = score_news_quality(
        current_quarter_news=_news(1, 2),
        prior_quarter_news=_news(1, 2),
        composition_shift="contracts_to_acquisitions",
    )
    baseline = score_news_quality(
        current_quarter_news=_news(1, 2),
        prior_quarter_news=_news(1, 2),
        composition_shift=None,
    )
    assert result.score == max(0, baseline.score - 5)


def test_score_capped_at_100():
    # extreme positive: prior=3pts, current=150pts
    result = score_news_quality(
        current_quarter_news=_news(1, 10),
        prior_quarter_news=_news(3, 1),
        composition_shift="acquisitions_to_contracts",
    )
    assert result.score <= 100


def test_score_floor_at_0():
    # very low score + negative modifier
    result = score_news_quality(
        current_quarter_news=[],
        prior_quarter_news=_news(1, 20),
        composition_shift="contracts_to_acquisitions",
    )
    assert result.score >= 0


def test_raw_inputs_populated():
    result = score_news_quality(
        current_quarter_news=_news(1, 1),
        prior_quarter_news=_news(2, 1),
        composition_shift=None,
    )
    assert "current_raw" in result.raw_inputs
    assert "prior_raw" in result.raw_inputs
    assert "delta_pct" in result.raw_inputs
