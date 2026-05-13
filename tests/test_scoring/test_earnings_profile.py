import pytest
from core.scoring.earnings_profile import score_earnings_profile


def test_track_a_selected_for_negative_eps():
    result = score_earnings_profile(eps_ttm=-1.0)
    assert result.raw_inputs["track"] == "A"


def test_track_b_selected_for_positive_eps():
    result = score_earnings_profile(eps_ttm=1.0)
    assert result.raw_inputs["track"] == "B"


def test_track_a_all_growth_indicators():
    # base=50 + 15+10+10+10+5 = 100
    result = score_earnings_profile(
        eps_ttm=-1.0,
        rd_increasing_gt10_pct=True,
        capex_rising=True,
        new_products_or_expansion=True,
        deferred_revenue_increasing=True,
        mgmt_framing_losses_as_investment=True,
    )
    assert result.score == 100


def test_track_a_all_decay_indicators():
    # base=50 - 20-15-15-10-10 = -20 → capped at 0
    result = score_earnings_profile(
        eps_ttm=-1.0,
        revenue_declining_while_losses_widen=True,
        sga_rising_faster_than_revenue=True,
        customer_churn_in_filings=True,
        no_new_product_pipeline=True,
        mgmt_guidance_vague_or_declining=True,
    )
    assert result.score == 0


def test_track_b_all_expansion_indicators():
    # base=50 + 15+10+10+10+5 = 100
    result = score_earnings_profile(
        eps_ttm=1.0,
        gross_margins_expanding_2q=True,
        opex_less_than_revenue_growth=True,
        eps_growth_accelerating=True,
        revenue_gt15_stable_margins=True,
        consensus_eps_below_run_rate=True,
    )
    assert result.score == 100


def test_track_b_all_compression_indicators():
    # base=50 - 20-15-15-10-10 = -20 → capped at 0
    result = score_earnings_profile(
        eps_ttm=1.0,
        gross_margins_declining_2q=True,
        sga_cogs_growing_faster=True,
        eps_growth_decelerating=True,
        consensus_eps_above_trajectory=True,
        mgmt_lowering_margin_guidance=True,
    )
    assert result.score == 0


def test_track_a_mixed_scenario():
    # base=50 + 15 (rd) - 20 (declining losses) = 45
    result = score_earnings_profile(
        eps_ttm=-1.0,
        rd_increasing_gt10_pct=True,
        revenue_declining_while_losses_widen=True,
    )
    assert result.score == 45


def test_track_b_mixed_scenario():
    # base=50 + 15 (margins expanding) - 20 (margins declining) = 45
    result = score_earnings_profile(
        eps_ttm=1.0,
        gross_margins_expanding_2q=True,
        gross_margins_declining_2q=True,
    )
    assert result.score == 45


def test_eps_exactly_zero_uses_track_b():
    result = score_earnings_profile(eps_ttm=0.0)
    assert result.raw_inputs["track"] == "B"


def test_base_score_is_50():
    result = score_earnings_profile(eps_ttm=1.0)
    assert result.raw_inputs["base"] == 50
    assert result.score == 50
