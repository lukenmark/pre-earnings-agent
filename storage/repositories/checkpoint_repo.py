from sqlalchemy.orm import Session

from models.checkpoint import CheckpointReport
from storage.tables import CheckpointRow


def save(db: Session, report: CheckpointReport) -> CheckpointRow:
    row = CheckpointRow(
        ticker=report.ticker,
        checkpoint=report.checkpoint,
        composite_score=report.composite_score,
        decision=report.decision,
        hypothesis_direction=report.hypothesis_direction,
        hard_veto=report.hard_veto,
        core_override_triggered=report.core_override_triggered,
        report_json=report.model_dump_json(),
        prior_composite_score=report.prior_composite_score,
        score_delta=report.score_delta,
        includes_mbp=report.includes_mbp,
        created_at=report.created_at,
    )
    db.add(row)
    db.flush()
    return row


def get_by_ticker(db: Session, ticker: str) -> list[CheckpointRow]:
    return (
        db.query(CheckpointRow)
        .filter(CheckpointRow.ticker == ticker)
        .order_by(CheckpointRow.created_at)
        .all()
    )


def get_latest(db: Session, ticker: str) -> CheckpointRow | None:
    return (
        db.query(CheckpointRow)
        .filter(CheckpointRow.ticker == ticker)
        .order_by(CheckpointRow.created_at.desc())
        .first()
    )


def get_trajectory(db: Session, ticker: str) -> list[tuple[str, int]]:
    rows = get_by_ticker(db, ticker)
    return [(r.checkpoint, r.composite_score) for r in rows]
