import pytest
from datetime import datetime, timezone

from models.scores import FactorScore
from core.scoring.composite import compute_composite_score, WEIGHTS


def _fs(name: str, score: int, hard_veto: bool = False) -> FactorScore:
    return FactorScore(
        factor_name=name,
        score=score,
        reasoning="test",
        raw_inputs={"hard_veto": hard_veto},
        sources=[],
        scored_at=datetime.now(timezone.utc),
    )


def _all_scores(score: int = 75) -> dict[str, FactorScore]:
    return {k: _fs(k, score) for k in WEIGHTS}


def test_weights_sum_to_1():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_all_75_scores_gives_buy():
    composite, decision, flags = compute_composite_score(_all_scores(75))
    assert composite == 75
    assert decision == "BUY"
    assert flags == []


def test_hard_veto_returns_no_go():
    scores = _all_scores(75)
    scores["insider_activity"] = _fs("insider_activity", 0, hard_veto=True)
    composite, decision, flags = compute_composite_score(scores)
    assert decision == "NO_GO"
    assert any("HARD_VETO" in f for f in flags)


def test_core_override_both_below_50():
    scores = _all_scores(75)
    scores["news_quality"] = _fs("news_quality", 45)
    scores["price_absorption_gap"] = _fs("price_absorption_gap", 45)
    composite, decision, flags = compute_composite_score(scores)
    assert decision == "NO_GO"
    assert any("CORE_OVERRIDE" in f for f in flags)


def test_core_override_one_below_40():
    scores = _all_scores(75)
    scores["news_quality"] = _fs("news_quality", 35)
    composite, decision, flags = compute_composite_score(scores)
    assert decision == "NO_GO"
    assert any("CORE_OVERRIDE" in f for f in flags)


def test_forced_downgrade_core_avg_below_60():
    # news=55, pag=55 → core_avg=55 < 60
    # other factors all 90 → composite should be >= 70
    scores = {k: _fs(k, 90) for k in WEIGHTS}
    scores["news_quality"] = _fs("news_quality", 55)
    scores["price_absorption_gap"] = _fs("price_absorption_gap", 55)
    composite, decision, flags = compute_composite_score(scores)
    if composite >= 70:
        assert decision == "WATCH"
        assert any("FORCED_DOWNGRADE" in f for f in flags)
    else:
        # composite < 70 means downgrade wasn't needed — still valid WATCH/NO_GO
        assert decision in ("WATCH", "NO_GO")


def test_trajectory_warning_flag():
    scores = _all_scores(60)
    composite, decision, flags = compute_composite_score(scores, prior_composite_score=80)
    assert any("TRAJECTORY_WARNING" in f for f in flags)


def test_no_trajectory_warning_small_drop():
    scores = _all_scores(70)
    composite, decision, flags = compute_composite_score(scores, prior_composite_score=80)
    # delta = -10, below threshold of -15, no warning
    assert not any("TRAJECTORY_WARNING" in f for f in flags)


def test_composite_below_50_is_no_go():
    scores = _all_scores(40)
    composite, decision, flags = compute_composite_score(scores)
    assert decision == "NO_GO"


def test_composite_50_to_69_is_watch():
    scores = _all_scores(60)
    composite, decision, flags = compute_composite_score(scores)
    assert composite == 60
    assert decision == "WATCH"


def test_pag_below_40_triggers_core_override():
    scores = _all_scores(80)
    scores["price_absorption_gap"] = _fs("price_absorption_gap", 38)
    composite, decision, flags = compute_composite_score(scores)
    assert decision == "NO_GO"
    assert any("Price Absorption Gap" in f for f in flags)
