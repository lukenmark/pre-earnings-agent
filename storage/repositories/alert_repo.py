import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models.alert import FinalAlert
from storage.tables import AlertRow


def save(db: Session, alert: FinalAlert) -> AlertRow:
    row = AlertRow(
        ticker=alert.ticker,
        company_name=alert.company_name,
        recommendation=alert.recommendation,
        composite_score=alert.composite_score,
        checkpoint_trajectory_json=json.dumps(alert.checkpoint_trajectory),
        thesis=alert.thesis,
        earnings_date=alert.earnings_date,
        alert_json=alert.model_dump_json(),
        hard_veto=alert.hard_veto,
        alert_sent_at=alert.alert_sent_at,
    )
    db.add(row)
    db.flush()
    return row


def get_active_buys(db: Session) -> list[AlertRow]:
    now = datetime.now(timezone.utc)
    return (
        db.query(AlertRow)
        .filter(AlertRow.recommendation == "BUY", AlertRow.earnings_date >= now)
        .all()
    )


def get_by_ticker(db: Session, ticker: str) -> list[AlertRow]:
    return db.query(AlertRow).filter(AlertRow.ticker == ticker).all()
