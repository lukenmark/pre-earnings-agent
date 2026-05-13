import pytest
from core.scoring.options_flow import score_options_flow


def test_extreme_bullish_all_max_points():
    # call_sizzle=7 (+40), put_sizzle=0 (0), vol_ask=70% (+25), vol_bid=0% (0), C/P=2.0 (+10), IV=80 (+10) = 85
    result = score_options_flow(
        call_sizzle_index=7.0,
        put_sizzle_index=0.5,
        volume_at_ask_pct=70.0,
        volume_at_bid_pct=10.0,
        call_put_ratio=2.0,
        iv_percentile=80.0,
    )
    assert result.score == 85


def test_put_sizzle_penalty_above_3():
    r_low = score_options_flow(3.0, 0.5, 50.0, 0.0, 1.0, 50.0)
    r_high = score_options_flow(3.0, 3.5, 50.0, 0.0, 1.0, 50.0)
    # put_sizzle >=3 subtracts 15 vs 0
    assert r_high.score == r_low.score - 15


def test_volume_at_bid_penalty():
    r_no = score_options_flow(3.0, 0.5, 55.0, 10.0, 1.0, 50.0)
    r_yes = score_options_flow(3.0, 0.5, 55.0, 65.0, 1.0, 50.0)
    # bid>=60% subtracts 20 vs 0
    assert r_yes.score == max(0, r_no.score - 20)


def test_score_capped_at_100():
    result = score_options_flow(
        call_sizzle_index=10.0,
        put_sizzle_index=0.0,
        volume_at_ask_pct=80.0,
        volume_at_bid_pct=0.0,
        call_put_ratio=3.0,
        iv_percentile=90.0,
    )
    assert result.score <= 100


def test_score_floor_at_0():
    # all negative: call_sizzle=0 (+5), put_sizzle=4 (-15), vol_ask=30 (+5), vol_bid=70 (-20), C/P=0.5 (-10), IV=20 (-5)
    # = 5-15+5-20-10-5 = -40 → floor 0
    result = score_options_flow(
        call_sizzle_index=0.5,
        put_sizzle_index=4.0,
        volume_at_ask_pct=30.0,
        volume_at_bid_pct=70.0,
        call_put_ratio=0.5,
        iv_percentile=20.0,
    )
    assert result.score == 0


def test_call_sizzle_tiers():
    r1 = score_options_flow(0.5, 0.5, 50.0, 0.0, 1.0, 50.0)   # < 1.5 → +5
    r2 = score_options_flow(2.0, 0.5, 50.0, 0.0, 1.0, 50.0)   # 1.5-3.0 → +20
    r3 = score_options_flow(4.0, 0.5, 50.0, 0.0, 1.0, 50.0)   # 3.0-6.0 → +30
    r4 = score_options_flow(7.0, 0.5, 50.0, 0.0, 1.0, 50.0)   # >=6.0 → +40
    assert r4.score > r3.score > r2.score > r1.score


def test_iv_below_40_penalty():
    r_mid = score_options_flow(3.0, 0.5, 55.0, 0.0, 1.0, 50.0)   # IV=50, no modifier
    r_low = score_options_flow(3.0, 0.5, 55.0, 0.0, 1.0, 30.0)   # IV=30, -5
    assert r_low.score == r_mid.score - 5


def test_raw_inputs_stored():
    result = score_options_flow(3.0, 0.5, 55.0, 0.0, 1.0, 50.0)
    assert "raw_points" in result.raw_inputs
    assert result.raw_inputs["call_sizzle_index"] == 3.0
