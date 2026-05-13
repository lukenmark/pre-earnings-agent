from datetime import date
from sqlalchemy.orm import Session

from models.watchlist import WatchlistEntry
from storage.tables import WatchlistRow


def get_all_active(db: Session) -> list[WatchlistRow]:
    return db.query(WatchlistRow).filter(
        WatchlistRow.status.in_(["candidate", "active", "buy_alert"])
    ).all()


def get_by_ticker(db: Session, ticker: str) -> WatchlistRow | None:
    return db.query(WatchlistRow).filter(WatchlistRow.ticker == ticker).first()


def add(db: Session, entry: WatchlistEntry) -> WatchlistRow:
    row = WatchlistRow(**entry.model_dump())
    db.add(row)
    db.flush()
    return row


def update_status(db: Session, ticker: str, status: str) -> None:
    db.query(WatchlistRow).filter(WatchlistRow.ticker == ticker).update({"status": status})


def update_earnings_date(db: Session, ticker: str, earnings_date: date) -> None:
    db.query(WatchlistRow).filter(WatchlistRow.ticker == ticker).update({"earnings_date": earnings_date})


def remove(db: Session, ticker: str) -> None:
    db.query(WatchlistRow).filter(WatchlistRow.ticker == ticker).update({"status": "completed"})
