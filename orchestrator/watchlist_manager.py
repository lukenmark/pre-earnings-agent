from datetime import date, datetime, timedelta

from models.watchlist import WatchlistEntry
from storage.database import get_db
from storage.repositories.watchlist_repo import (
    get_all_active, get_by_ticker, add, update_status, update_earnings_date
)
from storage.repositories.industry_repo import get_active as get_active_industries
from data.finviz_screener import screen_candidates
from data.yfinance_client import get_stock_info, get_market_cap
from orchestrator.fiscal_calendar import FiscalCalendar
from utils.logger import logger


class WatchlistManager:
    def __init__(self):
        self._active_industries: list[str] = []

    def refresh_active_industries(self) -> list[str]:
        """Load current active industry names from DB"""
        with get_db() as db:
            rows = get_active_industries(db)
            self._active_industries = [r.industry_name for r in rows] if rows else []
        logger.info(f"Active industries: {self._active_industries}")
        return self._active_industries

    def run_discovery_scan(self) -> list[dict]:
        """
        Full pipeline:
        1. Run Finviz screen → candidates (max 20)
        2. Cross-reference against active industries
        3. For each new candidate not already in watchlist:
           a. Fetch earnings date from yfinance
           b. Determine fiscal calendar
           c. Add to watchlist with status='candidate'
        4. Return list of new candidates added

        Returns list of dicts: {ticker, company_name, screen_score, industry_match, earnings_date}
        """
        logger.info("Starting discovery scan...")

        # 1. Run Finviz screen
        try:
            candidates = screen_candidates(industry_filter=self._active_industries)
        except Exception as e:
            logger.error(f"Finviz screen failed: {e}")
            candidates = []

        if not candidates:
            logger.warning("Discovery scan returned 0 candidates")
            return []

        logger.info(f"Finviz screen returned {len(candidates)} candidates")

        new_entries = []
        with get_db() as db:
            existing_tickers = {row.ticker for row in get_all_active(db)}

            for c in candidates[:20]:
                ticker = c.get("ticker", "")
                if not ticker or ticker in existing_tickers:
                    continue

                # Fetch earnings date and stock info
                info = {}
                try:
                    info = get_stock_info(ticker) or {}
                except Exception as e:
                    logger.warning(f"Could not fetch info for {ticker}: {e}")

                earnings_date = _parse_earnings_date(info.get("earningsDate") or info.get("earningsTimestamp"))
                fiscal_year_end = _infer_fiscal_year_end(info)
                industry_match = c.get("industry", "") in self._active_industries

                entry = WatchlistEntry(
                    ticker=ticker,
                    company_name=c.get("company", ticker),
                    earnings_date=earnings_date,
                    fiscal_year_end=fiscal_year_end,
                    status="candidate",
                    date_added=datetime.now(timezone.utc),
                    industry=c.get("industry"),
                    eps_ttm=c.get("eps_ttm"),
                    market_cap=c.get("market_cap"),
                    notes=f"screen_score={c.get('screen_score', 0):.0f}, industry_match={industry_match}",
                )

                try:
                    add(db, entry)
                    new_entries.append({
                        "ticker": ticker,
                        "company_name": entry.company_name,
                        "screen_score": c.get("screen_score", 0),
                        "industry_match": industry_match,
                        "earnings_date": earnings_date.isoformat() if earnings_date else None,
                    })
                    logger.info(f"Added {ticker} to watchlist (industry_match={industry_match})")
                except Exception as e:
                    logger.warning(f"Failed to add {ticker} to watchlist: {e}")

        logger.info(f"Discovery scan complete: {len(new_entries)} new candidates added")
        return new_entries

    def get_due_checkpoints(self, reference_date: date | None = None) -> list[dict]:
        """
        Returns tickers due for a checkpoint based on their earnings date.

        T-21: earnings_date - 21 days (±1 day window)
        T-14: earnings_date - 14 days (±1 day window)
        T-7:  earnings_date - 7 days (±1 day window)
        T-3:  earnings_date - 3 days (±1 day window)

        Returns list of {ticker, company_name, checkpoint, earnings_date}
        """
        ref = reference_date or date.today()
        due = []

        with get_db() as db:
            active = get_all_active(db)
            for row in active:
                if not row.earnings_date:
                    continue
                ed = row.earnings_date
                for days, label in [(21, "T-21"), (14, "T-14"), (7, "T-7"), (3, "T-3")]:
                    target = ed - timedelta(days=days)
                    if abs((ref - target).days) <= 1:
                        due.append({
                            "ticker": row.ticker,
                            "company_name": row.company_name,
                            "checkpoint": label,
                            "earnings_date": ed,
                        })
        return due

    def promote_candidate(self, ticker: str) -> None:
        """Move a ticker from 'candidate' → 'active'"""
        with get_db() as db:
            update_status(db, ticker, "active")

    def mark_no_go(self, ticker: str) -> None:
        with get_db() as db:
            update_status(db, ticker, "no_go")

    def mark_buy_alert(self, ticker: str) -> None:
        with get_db() as db:
            update_status(db, ticker, "buy_alert")

    def mark_completed(self, ticker: str) -> None:
        with get_db() as db:
            update_status(db, ticker, "completed")

    def refresh_earnings_dates(self) -> None:
        """Re-fetch earnings dates for all active watchlist entries"""
        with get_db() as db:
            active = get_all_active(db)
        for row in active:
            try:
                info = get_stock_info(row.ticker) or {}
                ed = _parse_earnings_date(info.get("earningsDate") or info.get("earningsTimestamp"))
                if ed:
                    with get_db() as db:
                        update_earnings_date(db, row.ticker, ed)
            except Exception as e:
                logger.warning(f"Could not refresh earnings date for {row.ticker}: {e}")


def _parse_earnings_date(raw) -> date | None:
    """Parse earnings date from various yfinance formats"""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]
    if isinstance(raw, date):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, (int, float)):
        try:
            return datetime.utcfromtimestamp(raw).date()
        except Exception:
            return None
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw[:10])
        except Exception:
            return None
    return None


def _infer_fiscal_year_end(info: dict) -> str | None:
    """Try to infer fiscal year end from yfinance info dict"""
    fy = info.get("fiscalYearEnd")
    if fy:
        return fy
    return None
