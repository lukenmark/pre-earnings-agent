from models.scores import FactorScore

WEIGHTS: dict[str, float] = {
    "news_quality": 0.20,
    "price_absorption_gap": 0.15,
    "industry_momentum": 0.15,
    "revenue_trend": 0.15,
    "earnings_profile": 0.10,
    "options_flow": 0.10,
    "insider_activity": 0.10,
    "cash_runway": 0.05,
}
# Sum = 1.0


def compute_composite_score(
    factor_scores: dict[str, FactorScore],
    prior_composite_score: int | None = None,
    sources: list[str] = [],
) -> tuple[int, str, list[str]]:
    flags: list[str] = []
    decision: str | None = None

    # Step 1: hard veto
    insider = factor_scores.get("insider_activity")
    if insider and insider.raw_inputs.get("hard_veto") is True:
        return (0, "NO_GO", ["HARD_VETO: Heavy discretionary insider selling detected"])

    # Step 2: weighted sum
    composite = sum(
        factor_scores[k].score * WEIGHTS[k]
        for k in WEIGHTS
        if k in factor_scores
    )
    composite = round(composite)

    # Step 3: core override rules
    news_score = factor_scores["news_quality"].score if "news_quality" in factor_scores else 0
    pag_score = factor_scores["price_absorption_gap"].score if "price_absorption_gap" in factor_scores else 0
    core_avg = (news_score + pag_score) / 2

    if news_score < 40 or pag_score < 40:
        failing = "News Quality" if news_score < 40 else "Price Absorption Gap"
        flags.append(f"CORE_OVERRIDE: {failing} scored below 40")
        return (composite, "NO_GO", flags)

    if news_score < 50 and pag_score < 50:
        flags.append("CORE_OVERRIDE: Both core factors below 50")
        return (composite, "NO_GO", flags)

    if core_avg < 60 and composite >= 70:
        flags.append(f"FORCED_DOWNGRADE: Core avg {core_avg:.0f} < 60 despite composite {composite} >= 70")
        decision = "WATCH"
        # fall through to trajectory check, then return with WATCH forced

    # Step 4: trajectory rule
    if prior_composite_score is not None:
        delta = composite - prior_composite_score
        if delta <= -15:
            flags.append(
                f"TRAJECTORY_WARNING: Score dropped {abs(delta)} points "
                f"from {prior_composite_score} to {composite}"
            )

    # Step 5: threshold decision (if not forced)
    if decision is None:
        if composite >= 70:
            decision = "BUY"
        elif composite >= 50:
            decision = "WATCH"
        else:
            decision = "NO_GO"

    return (composite, decision, flags)
