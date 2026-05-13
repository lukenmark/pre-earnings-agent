from datetime import datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class WatchlistRow(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    earnings_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    fiscal_year_end: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="candidate", nullable=False)
    date_added: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    eps_ttm: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)


class CheckpointRow(Base):
    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String, ForeignKey("watchlist.ticker"), index=True, nullable=False)
    checkpoint: Mapped[str] = mapped_column(String, nullable=False)
    composite_score: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    hypothesis_direction: Mapped[str] = mapped_column(String, nullable=False)
    hard_veto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    core_override_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    prior_composite_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    includes_mbp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class AlertRow(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String, index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    recommendation: Mapped[str] = mapped_column(String, nullable=False)
    composite_score: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_trajectory_json: Mapped[str] = mapped_column(Text, nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    earnings_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    alert_json: Mapped[str] = mapped_column(Text, nullable=False)
    hard_veto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alert_sent_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class FeedbackRow(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


class IndustryAssessmentRow(Base):
    __tablename__ = "industry_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    industry_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    composite_score: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    consecutive_low_weeks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RawDataCacheRow(Base):
    __tablename__ = "raw_data_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    data_type: Mapped[str] = mapped_column(String, nullable=False)
    ticker: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
