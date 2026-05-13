from sqlalchemy.orm import Session

from storage.tables import FeedbackRow


def save(db: Session, ticker: str, user_id: str, rating: int, notes: str | None) -> FeedbackRow:
    row = FeedbackRow(ticker=ticker, user_id=user_id, rating=rating, notes=notes)
    db.add(row)
    db.flush()
    return row


def get_by_ticker(db: Session, ticker: str) -> list[FeedbackRow]:
    return db.query(FeedbackRow).filter(FeedbackRow.ticker == ticker).all()


def get_all(db: Session) -> list[FeedbackRow]:
    return db.query(FeedbackRow).all()
