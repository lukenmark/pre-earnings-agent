import pytest
from core.scoring.price_absorption import score_price_absorption


def test_strong_news_price_down_no_cause():
    # news=80, price=-10%, suppression=none_identified → C1 high, multiplier 1.4 → high score
    result = score_price_absorption(
        quarterly_price_change_pct=-10.0,
        news_quality_score=80,
        suppression_cause="none_identified",
    )
    assert result.score >= 70


def test_strong_news_price_down_mechanical():
    result_mech = score_price_absorption(
        quarterly_price_change_pct=-10.0,
        news_quality_score=80,
        suppression_cause="mechanical",
    )
    result_none = score_price_absorption(
        quarterly_price_change_pct=-10.0,
        news_quality_score=80,
        suppression_cause="not_suppressed",
    )
    # mechanical multiplier 1.2 > not_suppressed 1.0, so mechanical should score higher
    assert result_mech.score >= result_none.score
    assert result_mech.raw_inputs["multiplier"] == 1.2


def test_strong_news_price_down_fundamental():
    result = score_price_absorption(
        quarterly_price_change_pct=-10.0,
        news_quality_score=80,
        suppression_cause="fundamental",
    )
    assert result.raw_inputs["multiplier"] == 0.5
    # fundamental should score lower than mechanical
    result_mech = score_price_absorption(
        quarterly_price_change_pct=-10.0,
        news_quality_score=80,
        suppression_cause="mechanical",
    )
    assert result.score < result_mech.score


def test_strong_news_price_massive_run():
    # news=80, price=+80% → C1 = 30 - (80-50)/50*30 = 12, in the 0-30 range
    result = score_price_absorption(
        quarterly_price_change_pct=80.0,
        news_quality_score=80,
        suppression_cause="not_suppressed",
    )
    assert result.raw_inputs["c1"] <= 30
    assert result.raw_inputs["c1"] < 20  # clearly low, not mid-range


def test_weak_news_neutral():
    # news=40 (< 60) → C1=50 regardless
    result = score_price_absorption(
        quarterly_price_change_pct=-5.0,
        news_quality_score=40,
        suppression_cause="not_suppressed",
    )
    assert result.raw_inputs["c1"] == 50.0


def test_formula_aggregation():
    result = score_price_absorption(
        quarterly_price_change_pct=0.0,
        news_quality_score=80,
        suppression_cause="not_suppressed",
    )
    c1 = result.raw_inputs["c1"]
    c2 = result.raw_inputs["c2_adjusted"]
    c3 = result.raw_inputs["c3"]
    expected = int(max(0, min(100, c1 * 0.50 + c2 * 0.30 + c3 * 0.20)))
    assert result.score == expected


def test_score_capped_0_100():
    result = score_price_absorption(
        quarterly_price_change_pct=-30.0,
        news_quality_score=100,
        suppression_cause="none_identified",
    )
    assert 0 <= result.score <= 100


def test_none_identified_highest_multiplier():
    r_none = score_price_absorption(-10.0, 80, "none_identified")
    r_mech = score_price_absorption(-10.0, 80, "mechanical")
    r_fund = score_price_absorption(-10.0, 80, "fundamental")
    assert r_none.score >= r_mech.score >= r_fund.score
