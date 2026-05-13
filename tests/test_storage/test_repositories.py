"""CRUD round-trip tests for all storage repositories."""
import json
from datetime import datetime, timezone, date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from storage.tables import Base
from models.watchlist import WatchlistEntry
from models.alert import FinalAlert
from models.checkpoint import CheckpointReport
from models.scores import FactorScore
from models.industry import IndustryAssessment

import storage.repositories.watchlist_repo as watchlist_repo
import storage.repositories.alert_repo as alert_repo
import storage.repositories.checkpoint_repo as checkpoint_repo
import storage.repositories.feedback_repo as feedback_repo
import storage.repositories.industry_repo as industry_repo


@pytest.fixture(scope="module")
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session_ = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session_()
    yield session
    session.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Watchlist ────────────────────────────────────────────────────────────────

class TestWatchlistRepo:
    def test_add_and_get(self, db):
        entry = WatchlistEntry(
            ticker="AAPL",
            company_name="Apple Inc.",
            earnings_date=date(2026, 1, 30),
            status="candidate",
            date_added=_now(),
            industry="Technology",
        )
        row = watchlist_repo.add(db, entry)
        db.commit()
        assert row.id is not None
        assert row.ticker == "AAPL"

        fetched = watchlist_repo.get_by_ticker(db, "AAPL")
        assert fetched is not None
        assert fetched.company_name == "Apple Inc."
        assert fetched.industry == "Technology"

    def test_get_all_active(self, db):
        entry = WatchlistEntry(
            ticker="MSFT",
            company_name="Microsoft Corp.",
            status="active",
            date_added=_now(),
        )
        watchlist_repo.add(db, entry)
        db.commit()

        active = watchlist_repo.get_all_active(db)
        tickers = [r.ticker for r in active]
        assert "MSFT" in tickers

    def test_update_status(self, db):
        watchlist_repo.update_status(db, "AAPL", "buy_alert")
        db.commit()
        row = watchlist_repo.get_by_ticker(db, "AAPL")
        assert row.status == "buy_alert"

    def test_update_earnings_date(self, db):
        new_date = date(2026, 2, 14)
        watchlist_repo.update_earnings_date(db, "AAPL", new_date)
        db.commit()
        row = watchlist_repo.get_by_ticker(db, "AAPL")
        assert row.earnings_date == new_date

    def test_remove_sets_completed(self, db):
        watchlist_repo.remove(db, "AAPL")
        db.commit()
        row = watchlist_repo.get_by_ticker(db, "AAPL")
        assert row.status == "completed"

    def test_missing_ticker_returns_none(self, db):
        result = watchlist_repo.get_by_ticker(db, "ZZZZ")
        assert result is None


# ── Checkpoint ───────────────────────────────────────────────────────────────

class TestCheckpointRepo:
    def _make_report(self, ticker: str, checkpoint: str, score: int, prior: int | None = None) -> CheckpointReport:
        fs = FactorScore(
            factor_name="revenue_trend",
            score=score,
            reasoning="steady revenue growth",
            raw_inputs={"q1": 1.0, "q2": 1.1},
            sources=["yfinance"],
            scored_at=_now(),
        )
        return CheckpointReport(
            ticker=ticker,
            checkpoint=checkpoint,
            composite_score=score,
            decision="WATCH",
            hypothesis_direction="bullish",
            factor_scores={"revenue_trend": fs},
            key_findings=["revenue up"],
            flags=[],
            prior_composite_score=prior,
            created_at=_now(),
        )

    def test_save_and_get(self, db):
        # MSFT was added in watchlist tests above
        report = self._make_report("MSFT", "T-21", 65)
        row = checkpoint_repo.save(db, report)
        db.commit()
        assert row.id is not None
        assert row.composite_score == 65

        rows = checkpoint_repo.get_by_ticker(db, "MSFT")
        assert len(rows) >= 1
        assert rows[0].ticker == "MSFT"

    def test_get_latest(self, db):
        report2 = self._make_report("MSFT", "T-14", 72, prior=65)
        checkpoint_repo.save(db, report2)
        db.commit()

        latest = checkpoint_repo.get_latest(db, "MSFT")
        assert latest is not None
        assert latest.checkpoint == "T-14"
        assert latest.composite_score == 72

    def test_score_delta_stored(self, db):
        latest = checkpoint_repo.get_latest(db, "MSFT")
        assert latest.score_delta == 7  # 72 - 65

    def test_get_trajectory(self, db):
        traj = checkpoint_repo.get_trajectory(db, "MSFT")
        assert len(traj) >= 2
        checkpoints = [t[0] for t in traj]
        assert "T-21" in checkpoints
        assert "T-14" in checkpoints

    def test_no_checkpoints_returns_empty(self, db):
        rows = checkpoint_repo.get_by_ticker(db, "NOTEXIST")
        assert rows == []

    def test_get_latest_none_when_missing(self, db):
        result = checkpoint_repo.get_latest(db, "NOTEXIST")
        assert result is None


# ── Alert ────────────────────────────────────────────────────────────────────

class TestAlertRepo:
    def _make_alert(self, ticker: str, recommendation: str) -> FinalAlert:
        return FinalAlert(
            ticker=ticker,
            company_name=f"{ticker} Corp",
            recommendation=recommendation,
            composite_score=78,
            checkpoint_trajectory=[60, 68, 72, 78],
            core_news_score=75,
            core_pag_score=80,
            insider_summary="No insider selling",
            options_snapshot="IV elevated",
            share_structure_summary="Low float",
            thesis="Strong momentum into earnings",
            earnings_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
            alert_sent_at=_now(),
            hard_veto=False,
        )

    def test_save_buy_alert(self, db):
        alert = self._make_alert("NVDA", "BUY")
        row = alert_repo.save(db, alert)
        db.commit()
        assert row.id is not None
        assert row.recommendation == "BUY"
        assert row.ticker == "NVDA"

    def test_save_nogo_alert(self, db):
        alert = self._make_alert("TSLA", "NO_GO")
        row = alert_repo.save(db, alert)
        db.commit()
        assert row.recommendation == "NO_GO"

    def test_get_active_buys(self, db):
        buys = alert_repo.get_active_buys(db)
        tickers = [r.ticker for r in buys]
        assert "NVDA" in tickers
        assert "TSLA" not in tickers

    def test_get_by_ticker(self, db):
        rows = alert_repo.get_by_ticker(db, "NVDA")
        assert len(rows) >= 1
        assert rows[0].ticker == "NVDA"

    def test_checkpoint_trajectory_roundtrips(self, db):
        rows = alert_repo.get_by_ticker(db, "NVDA")
        traj = json.loads(rows[0].checkpoint_trajectory_json)
        assert traj == [60, 68, 72, 78]

    def test_get_by_missing_ticker(self, db):
        rows = alert_repo.get_by_ticker(db, "NOTEXIST")
        assert rows == []


# ── Feedback ─────────────────────────────────────────────────────────────────

class TestFeedbackRepo:
    def test_save_and_get(self, db):
        row = feedback_repo.save(db, "NVDA", "user_1", 5, "Great call!")
        db.commit()
        assert row.id is not None
        assert row.rating == 5

        rows = feedback_repo.get_by_ticker(db, "NVDA")
        assert len(rows) >= 1
        assert rows[0].notes == "Great call!"

    def test_save_without_notes(self, db):
        row = feedback_repo.save(db, "NVDA", "user_2", 3, None)
        db.commit()
        assert row.notes is None

    def test_get_all(self, db):
        all_rows = feedback_repo.get_all(db)
        assert len(all_rows) >= 2

    def test_empty_ticker_feedback(self, db):
        rows = feedback_repo.get_by_ticker(db, "NOTEXIST")
        assert rows == []


# ── Industry ─────────────────────────────────────────────────────────────────

class TestIndustryRepo:
    def _make_assessment(self, name: str, score: int, status: str = "active") -> IndustryAssessment:
        return IndustryAssessment(
            industry_name=name,
            composite_score=score,
            metrics={"sector_etf_fund_flows": score, "vc_private_capital_inflow": score},
            status=status,
            consecutive_low_weeks=0,
            assessed_at=_now(),
        )

    def test_save_and_get_active(self, db):
        a = self._make_assessment("Semiconductors", 80)
        row = industry_repo.save(db, a)
        db.commit()
        assert row.id is not None

        active = industry_repo.get_active(db)
        names = [r.industry_name for r in active]
        assert "Semiconductors" in names

    def test_get_latest_by_name(self, db):
        a2 = self._make_assessment("Semiconductors", 85)
        industry_repo.save(db, a2)
        db.commit()

        latest = industry_repo.get_latest_by_name(db, "Semiconductors")
        assert latest is not None
        assert latest.composite_score == 85

    def test_get_history(self, db):
        history = industry_repo.get_history(db, "Semiconductors")
        assert len(history) >= 2
        scores = [r.composite_score for r in history]
        assert 80 in scores and 85 in scores

    def test_dropped_not_in_active(self, db):
        a = self._make_assessment("Retail", 40, status="dropped")
        industry_repo.save(db, a)
        db.commit()

        active = industry_repo.get_active(db)
        names = [r.industry_name for r in active]
        assert "Retail" not in names

    def test_metrics_roundtrip(self, db):
        latest = industry_repo.get_latest_by_name(db, "Semiconductors")
        metrics = json.loads(latest.metrics_json)
        assert "sector_etf_fund_flows" in metrics

    def test_missing_industry_returns_none(self, db):
        result = industry_repo.get_latest_by_name(db, "Nonexistent Industry")
        assert result is None
