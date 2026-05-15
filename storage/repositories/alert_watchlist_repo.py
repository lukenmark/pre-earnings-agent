from datetime import datetime, timezone

from sqlalchemy.orm import Session

from storage.tables import AlertWatchlistRow


def get_all(db: Session) -> list[AlertWatchlistRow]:
    return db.query(AlertWatchlistRow).order_by(AlertWatchlistRow.added_at).all()


def get_by_ticker(db: Session, ticker: str) -> AlertWatchlistRow | None:
    return db.query(AlertWatchlistRow).filter(AlertWatchlistRow.ticker == ticker.upper()).first()


def add(db: Session, ticker: str, company_name: str, notes: str | None = None) -> AlertWatchlistRow:
    row = AlertWatchlistRow(
        ticker=ticker.upper(),
        company_name=company_name,
        added_at=datetime.now(timezone.utc),
        notes=notes,
    )
    db.add(row)
    db.flush()
    return row


def remove(db: Session, ticker: str) -> bool:
    row = get_by_ticker(db, ticker)
    if row:
        db.delete(row)
        db.flush()
        return True
    return False


def update_last_checked(db: Session, ticker: str) -> None:
    row = get_by_ticker(db, ticker)
    if row:
        row.last_checked_at = datetime.now(timezone.utc)
        db.flush()
