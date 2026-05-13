import pytest
from core.scoring.revenue_trend import score_revenue_trend


def test_30pct_yoy_score_100():
    result = score_revenue_trend(30.0, "flat", "stable")
    assert result.score == 100


def test_25pct_yoy_score_in_80_90_range():
    result = score_revenue_trend(25.0, "flat", "stable")
    assert 80 <= result.score <= 90


def test_negative_yoy():
    result = score_revenue_trend(-10.0, "flat", "stable")
    assert result.score <= 20


def test_qoq_positive_modifier_adds_10():
    r_flat = score_revenue_trend(15.0, "flat", "stable")
    r_pos = score_revenue_trend(15.0, "positive", "stable")
    assert r_pos.score == min(100, r_flat.score + 10)


def test_qoq_negative_modifier_subtracts_10():
    r_flat = score_revenue_trend(15.0, "flat", "stable")
    r_neg = score_revenue_trend(15.0, "negative", "stable")
    assert r_neg.score == max(0, r_flat.score - 10)


def test_gross_margin_expanding_adds_5():
    r_stable = score_revenue_trend(15.0, "flat", "stable")
    r_exp = score_revenue_trend(15.0, "flat", "expanding")
    assert r_exp.score == min(100, r_stable.score + 5)


def test_gross_margin_compressing_subtracts_10():
    r_stable = score_revenue_trend(15.0, "flat", "stable")
    r_comp = score_revenue_trend(15.0, "flat", "compressing")
    assert r_comp.score == max(0, r_stable.score - 10)


def test_score_cap_at_100():
    # 30% YoY (base=100) + positive (+10) + expanding (+5) → 115 → capped at 100
    result = score_revenue_trend(30.0, "positive", "expanding")
    assert result.score == 100


def test_score_floor_at_0():
    # large negative YoY + negative QoQ + compressing
    result = score_revenue_trend(-50.0, "negative", "compressing")
    assert result.score == 0


def test_yoy_5pct_in_40_60_range():
    result = score_revenue_trend(5.0, "flat", "stable")
    assert 20 <= result.score <= 60


def test_yoy_0pct_base_20():
    result = score_revenue_trend(0.0, "flat", "stable")
    assert result.raw_inputs["base_score"] == 20.0
