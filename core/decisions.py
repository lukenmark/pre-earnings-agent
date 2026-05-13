from datetime import datetime, timezone

from models.checkpoint import CheckpointReport
from models.scores import FactorScore
from core.scoring.composite import compute_composite_score


def make_decision(
    ticker: str,
    checkpoint: str,
    factor_scores: dict[str, FactorScore],
    prior_composite_score: int | None = None,
    hypothesis_direction: str = "neutral",
    includes_mbp: bool = False,
) -> CheckpointReport:
    composite, decision, flags = compute_composite_score(factor_scores, prior_composite_score)

    hard_veto = (
        factor_scores["insider_activity"].raw_inputs.get("hard_veto", False)
        if "insider_activity" in factor_scores
        else False
    )
    core_override = any("CORE_OVERRIDE" in f or "FORCED_DOWNGRADE" in f for f in flags)
    score_delta = (composite - prior_composite_score) if prior_composite_score is not None else None

    return CheckpointReport(
        ticker=ticker,
        checkpoint=checkpoint,
        composite_score=composite,
        decision=decision,
        hypothesis_direction=hypothesis_direction,
        hard_veto=hard_veto,
        core_override_triggered=core_override,
        factor_scores=factor_scores,
        key_findings=[],
        flags=flags,
        prior_composite_score=prior_composite_score,
        score_delta=score_delta,
        includes_mbp=includes_mbp,
        created_at=datetime.now(timezone.utc),
    )
