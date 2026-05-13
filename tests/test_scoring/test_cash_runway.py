import pytest
from core.scoring.cash_runway import score_cash_runway


def test_cash_flow_positive_burn_zero():
    result = score_cash_runway(1_000_000, 0)
    assert result.score == 100


def test_cash_flow_positive_burn_negative():
    # negative burn = generating cash
    result = score_cash_runway(1_000_000, -50_000)
    assert result.score == 100


def test_above_6_quarters():
    result = score_cash_runway(7_000_000, 1_000_000)  # 7 quarters
    assert result.score == 100


def test_4_to_6_quarters():
    result = score_cash_runway(5_000_000, 1_000_000)  # 5 quarters
    assert result.score == 70


def test_2_to_4_quarters():
    result = score_cash_runway(3_000_000, 1_000_000)  # 3 quarters
    assert result.score == 40


def test_below_2_quarters():
    result = score_cash_runway(1_500_000, 1_000_000)  # 1.5 quarters
    assert result.score == 10


def test_exactly_6_quarters():
    result = score_cash_runway(6_000_000, 1_000_000)
    assert result.score == 100


def test_exactly_4_quarters():
    result = score_cash_runway(4_000_000, 1_000_000)
    assert result.score == 70


def test_exactly_2_quarters():
    result = score_cash_runway(2_000_000, 1_000_000)
    assert result.score == 40


def test_quarters_stored_in_raw_inputs():
    result = score_cash_runway(5_000_000, 1_000_000)
    assert result.raw_inputs["quarters_runway"] == pytest.approx(5.0)
