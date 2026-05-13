import pytest
from core.scoring.insider_activity import score_insider_activity


def test_hard_veto_triggered():
    result = score_insider_activity(
        open_market_buys_detected=False,
        heavy_discretionary_selling=True,
        small_discretionary_selling=False,
    )
    assert result.score == 0
    assert result.raw_inputs["hard_veto"] is True


def test_open_market_buys():
    result = score_insider_activity(
        open_market_buys_detected=True,
        heavy_discretionary_selling=False,
        small_discretionary_selling=False,
    )
    assert result.score == 100


def test_small_discretionary_selling():
    result = score_insider_activity(
        open_market_buys_detected=False,
        heavy_discretionary_selling=False,
        small_discretionary_selling=True,
    )
    assert result.score == 30


def test_no_activity():
    result = score_insider_activity(
        open_market_buys_detected=False,
        heavy_discretionary_selling=False,
        small_discretionary_selling=False,
    )
    assert result.score == 60


def test_hard_veto_overrides_buys():
    # even with open market buys, hard veto wins
    result = score_insider_activity(
        open_market_buys_detected=True,
        heavy_discretionary_selling=True,
        small_discretionary_selling=False,
    )
    assert result.score == 0
    assert result.raw_inputs["hard_veto"] is True


def test_hard_veto_reasoning_contains_marker():
    result = score_insider_activity(
        open_market_buys_detected=False,
        heavy_discretionary_selling=True,
        small_discretionary_selling=False,
    )
    assert "HARD_VETO_TRIGGERED" in result.reasoning


def test_no_hard_veto_in_raw_inputs_when_clean():
    result = score_insider_activity(
        open_market_buys_detected=True,
        heavy_discretionary_selling=False,
        small_discretionary_selling=False,
    )
    assert result.raw_inputs["hard_veto"] is False
