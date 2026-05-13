from datetime import datetime, timezone

from models.scores import FactorScore


def score_options_flow(
    call_sizzle_index: float,
    put_sizzle_index: float,
    volume_at_ask_pct: float,
    volume_at_bid_pct: float,
    call_put_ratio: float,
    iv_percentile: float,
    sources: list[str] = [],
) -> FactorScore:
    points = 0
    breakdown: list[str] = []

    # Call sizzle
    if call_sizzle_index >= 6.0:
        pts = 40
    elif call_sizzle_index >= 3.0:
        pts = 30
    elif call_sizzle_index >= 1.5:
        pts = 20
    else:
        pts = 5
    points += pts
    breakdown.append(f"call_sizzle={call_sizzle_index}: {pts:+d}")

    # Put sizzle (subtract)
    if put_sizzle_index >= 3.0:
        pts = -15
    elif put_sizzle_index >= 1.5:
        pts = -5
    else:
        pts = 0
    points += pts
    breakdown.append(f"put_sizzle={put_sizzle_index}: {pts:+d}")

    # Volume at ask
    if volume_at_ask_pct >= 60:
        pts = 25
    elif volume_at_ask_pct >= 50:
        pts = 15
    else:
        pts = 5
    points += pts
    breakdown.append(f"vol_at_ask={volume_at_ask_pct}%: {pts:+d}")

    # Volume at bid (subtract)
    if volume_at_bid_pct >= 60:
        pts = -20
    elif volume_at_bid_pct >= 50:
        pts = -10
    else:
        pts = 0
    points += pts
    breakdown.append(f"vol_at_bid={volume_at_bid_pct}%: {pts:+d}")

    # Call/put ratio
    if call_put_ratio >= 1.5:
        pts = 10
    elif call_put_ratio >= 1.0:
        pts = 5
    elif call_put_ratio < 0.8:
        pts = -10
    else:
        pts = 0
    points += pts
    breakdown.append(f"call_put_ratio={call_put_ratio}: {pts:+d}")

    # IV percentile
    if iv_percentile >= 70:
        pts = 10
    elif iv_percentile < 40:
        pts = -5
    else:
        pts = 0
    points += pts
    breakdown.append(f"iv_percentile={iv_percentile}: {pts:+d}")

    score = max(0, min(100, points))

    reasoning = (
        f"Point accumulation: {'; '.join(breakdown)}. "
        f"Raw total={points}, final score={score}."
    )

    return FactorScore(
        factor_name="options_flow",
        score=score,
        reasoning=reasoning,
        raw_inputs={
            "call_sizzle_index": call_sizzle_index,
            "put_sizzle_index": put_sizzle_index,
            "volume_at_ask_pct": volume_at_ask_pct,
            "volume_at_bid_pct": volume_at_bid_pct,
            "call_put_ratio": call_put_ratio,
            "iv_percentile": iv_percentile,
            "raw_points": points,
        },
        sources=sources,
        scored_at=datetime.now(timezone.utc),
    )
