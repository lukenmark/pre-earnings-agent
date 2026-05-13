from datetime import datetime, timezone

from models.scores import FactorScore

TRACK_A_GROWTH = {
    "rd_increasing_gt10_pct": 15,
    "capex_rising": 10,
    "new_products_or_expansion": 10,
    "deferred_revenue_increasing": 10,
    "mgmt_framing_losses_as_investment": 5,
}

TRACK_A_DECAY = {
    "revenue_declining_while_losses_widen": -20,
    "sga_rising_faster_than_revenue": -15,
    "customer_churn_in_filings": -15,
    "no_new_product_pipeline": -10,
    "mgmt_guidance_vague_or_declining": -10,
}

TRACK_B_EXPANSION = {
    "gross_margins_expanding_2q": 15,
    "opex_less_than_revenue_growth": 10,
    "eps_growth_accelerating": 10,
    "revenue_gt15_stable_margins": 10,
    "consensus_eps_below_run_rate": 5,
}

TRACK_B_COMPRESSION = {
    "gross_margins_declining_2q": -20,
    "sga_cogs_growing_faster": -15,
    "eps_growth_decelerating": -15,
    "consensus_eps_above_trajectory": -10,
    "mgmt_lowering_margin_guidance": -10,
}


def score_earnings_profile(
    eps_ttm: float,
    rd_increasing_gt10_pct: bool = False,
    capex_rising: bool = False,
    new_products_or_expansion: bool = False,
    deferred_revenue_increasing: bool = False,
    mgmt_framing_losses_as_investment: bool = False,
    revenue_declining_while_losses_widen: bool = False,
    sga_rising_faster_than_revenue: bool = False,
    customer_churn_in_filings: bool = False,
    no_new_product_pipeline: bool = False,
    mgmt_guidance_vague_or_declining: bool = False,
    gross_margins_expanding_2q: bool = False,
    opex_less_than_revenue_growth: bool = False,
    eps_growth_accelerating: bool = False,
    revenue_gt15_stable_margins: bool = False,
    consensus_eps_below_run_rate: bool = False,
    gross_margins_declining_2q: bool = False,
    sga_cogs_growing_faster: bool = False,
    eps_growth_decelerating: bool = False,
    consensus_eps_above_trajectory: bool = False,
    mgmt_lowering_margin_guidance: bool = False,
    sources: list[str] = [],
) -> FactorScore:
    base = 50
    running = base
    applied: list[str] = []

    if eps_ttm < 0:
        track = "A"
        flags = {
            "rd_increasing_gt10_pct": rd_increasing_gt10_pct,
            "capex_rising": capex_rising,
            "new_products_or_expansion": new_products_or_expansion,
            "deferred_revenue_increasing": deferred_revenue_increasing,
            "mgmt_framing_losses_as_investment": mgmt_framing_losses_as_investment,
            "revenue_declining_while_losses_widen": revenue_declining_while_losses_widen,
            "sga_rising_faster_than_revenue": sga_rising_faster_than_revenue,
            "customer_churn_in_filings": customer_churn_in_filings,
            "no_new_product_pipeline": no_new_product_pipeline,
            "mgmt_guidance_vague_or_declining": mgmt_guidance_vague_or_declining,
        }
        point_map = {**TRACK_A_GROWTH, **TRACK_A_DECAY}
    else:
        track = "B"
        flags = {
            "gross_margins_expanding_2q": gross_margins_expanding_2q,
            "opex_less_than_revenue_growth": opex_less_than_revenue_growth,
            "eps_growth_accelerating": eps_growth_accelerating,
            "revenue_gt15_stable_margins": revenue_gt15_stable_margins,
            "consensus_eps_below_run_rate": consensus_eps_below_run_rate,
            "gross_margins_declining_2q": gross_margins_declining_2q,
            "sga_cogs_growing_faster": sga_cogs_growing_faster,
            "eps_growth_decelerating": eps_growth_decelerating,
            "consensus_eps_above_trajectory": consensus_eps_above_trajectory,
            "mgmt_lowering_margin_guidance": mgmt_lowering_margin_guidance,
        }
        point_map = {**TRACK_B_EXPANSION, **TRACK_B_COMPRESSION}

    for indicator, is_set in flags.items():
        if is_set:
            pts = point_map[indicator]
            running += pts
            applied.append(f"{indicator}: {pts:+d} → running {running}")

    score = max(0, min(100, running))

    reasoning = (
        f"Track {track} (eps_ttm={eps_ttm}). Base=50. "
        + ("; ".join(applied) if applied else "No indicators triggered")
        + f". Raw total={running}, final score={score}."
    )

    return FactorScore(
        factor_name="earnings_profile",
        score=score,
        reasoning=reasoning,
        raw_inputs={
            "eps_ttm": eps_ttm,
            "track": track,
            "base": base,
            "raw_total": running,
            "applied_indicators": applied,
        },
        sources=sources,
        scored_at=datetime.now(timezone.utc),
    )
