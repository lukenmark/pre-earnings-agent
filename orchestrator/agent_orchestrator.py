from datetime import date, datetime, timezone

from models.alert import FinalAlert
from models.checkpoint import CheckpointReport
from models.industry import IndustryAssessment
from models.scores import FactorScore
from storage.database import get_db
from storage.repositories.checkpoint_repo import save as save_checkpoint, get_latest, get_trajectory
from storage.repositories.alert_repo import save as save_alert
from storage.repositories.watchlist_repo import get_by_ticker, get_all_active
from storage.repositories.industry_repo import save as save_industry, get_active as get_active_industries
from orchestrator.watchlist_manager import WatchlistManager
from orchestrator.fiscal_calendar import FiscalCalendar
from core.analysis.financial_deep_dive import run_financial_deep_dive, extract_financial_inputs_for_scoring
from core.analysis.news_tiering import tier_news_with_llm
from core.analysis.share_structure import assess_share_structure
from core.analysis.mbp import generate_mbp
from core.scoring.news_quality import score_news_quality
from core.scoring.price_absorption import score_price_absorption
from core.scoring.revenue_trend import score_revenue_trend
from core.scoring.earnings_profile import score_earnings_profile
from core.scoring.cash_runway import score_cash_runway
from core.scoring.insider_activity import score_insider_activity
from core.scoring.options_flow import score_options_flow
from core.scoring.industry_momentum import score_industry_momentum
from core.decisions import make_decision
from data.yfinance_client import get_quarterly_price_change, get_market_cap, get_stock_info
from data.edgar_client import get_form4_filings
from data.factory import get_options_provider, get_industry_provider
from utils.logger import logger


class AgentOrchestrator:
    def __init__(self):
        self.watchlist_mgr = WatchlistManager()

    # ── Discovery ────────────────────────────────────────────

    def run_discovery(self) -> list[dict]:
        """Run Finviz screen, add new candidates to watchlist"""
        self.watchlist_mgr.refresh_active_industries()
        return self.watchlist_mgr.run_discovery_scan()

    # ── Industry Assessment ───────────────────────────────────

    def run_industry_assessment(self, industry_name: str) -> IndustryAssessment:
        """
        Fetch and score a single industry. Saves snapshot to DB.
        Checks drop rule: if score < 40 for 2 consecutive weekly snapshots → mark dropped.
        """
        provider = get_industry_provider()
        raw_metrics = provider.get_metrics(industry_name)

        assessment = IndustryAssessment(
            industry_name=industry_name,
            composite_score=0,
            metrics=raw_metrics,
            status="active",
            consecutive_low_weeks=0,
            assessed_at=datetime.now(timezone.utc),
        )
        assessment.composite_score = int(assessment.compute_composite())

        # Check drop rule
        with get_db() as db:
            from storage.repositories.industry_repo import get_history
            history = get_history(db, industry_name)
            recent_low = sum(1 for h in history[-2:] if h.composite_score < 40)
            if assessment.composite_score < 40:
                if recent_low >= 1:
                    assessment.consecutive_low_weeks = 2
                    assessment.status = "dropped"
                    logger.warning(f"Industry '{industry_name}' dropped — score {assessment.composite_score} < 40 for 2 consecutive weeks")
                else:
                    assessment.consecutive_low_weeks = 1
            save_industry(db, assessment)

        return assessment

    # ── Full Checkpoint Analysis ──────────────────────────────

    def run_checkpoint(
        self,
        ticker: str,
        checkpoint: str,  # "T-21" | "T-14" | "T-7" | "T-3"
        force: bool = False,
    ) -> CheckpointReport:
        """
        Run a full checkpoint analysis for a ticker.

        - T-21: financial deep dive + news tiering + share structure + MBP
        - T-14: news tiering + price absorption update
        - T-7:  news tiering + price absorption update + re-score all factors
        - T-3:  full re-score + insider activity (Form 4) + options flow → final decision

        Saves CheckpointReport to DB. Returns the report.
        """
        logger.info(f"Running {checkpoint} checkpoint for {ticker}")

        with get_db() as db:
            wl_row = get_by_ticker(db, ticker)
            if wl_row:
                company_name = wl_row.company_name
                eps_ttm = wl_row.eps_ttm
                market_cap = wl_row.market_cap
                earnings_date = wl_row.earnings_date
                fiscal_year_end = wl_row.fiscal_year_end
                industry = wl_row.industry
                wl_status = wl_row.status
            else:
                company_name = ticker
                eps_ttm = None
                market_cap = None
                earnings_date = None
                fiscal_year_end = None
                industry = None
                wl_status = None

        if not wl_row and not force:
            raise ValueError(f"{ticker} not found in watchlist")

        if market_cap is None:
            try:
                market_cap = get_market_cap(ticker)
            except Exception:
                pass

        # Get prior checkpoint score for trajectory
        with get_db() as db:
            prior_cp = get_latest(db, ticker)
            prior_composite = prior_cp.composite_score if prior_cp else None

        factor_scores: dict[str, FactorScore] = {}
        key_findings: list[str] = []
        includes_mbp = False

        # ── Step 1: Financial Deep Dive (T-21 and T-7) ──────
        deep_dive = None
        if checkpoint in ("T-21", "T-7"):
            try:
                deep_dive = run_financial_deep_dive(ticker, company_name, eps_ttm)
                if deep_dive.get("error"):
                    logger.warning(f"Deep dive partial for {ticker}: {deep_dive['error']}")
                key_findings += deep_dive.get("key_strengths", [])[:2]
                key_findings += [f"RISK: {r}" for r in deep_dive.get("key_risks", [])[:2]]
            except Exception as e:
                logger.warning(f"Financial deep dive failed for {ticker}: {e}")

        # ── Step 2: Revenue Trend ────────────────────────────
        yoy_pct, qoq_dir, gm_trend = _extract_revenue_inputs(deep_dive, ticker, eps_ttm)
        try:
            factor_scores["revenue_trend"] = score_revenue_trend(
                yoy_growth_pct=yoy_pct,
                qoq_direction=qoq_dir,
                gross_margin_trend=gm_trend,
                sources=["SEC EDGAR 10-Q"],
            )
        except Exception as e:
            logger.warning(f"revenue_trend scoring failed for {ticker}: {e}")

        # ── Step 3: Earnings Profile ─────────────────────────
        ep_inputs = {}
        if deep_dive:
            try:
                ep_inputs = extract_financial_inputs_for_scoring(deep_dive)
            except Exception as e:
                logger.warning(f"extract_financial_inputs failed for {ticker}: {e}")
        eps_val = eps_ttm if eps_ttm is not None else 0.0
        try:
            factor_scores["earnings_profile"] = score_earnings_profile(
                eps_ttm=eps_val,
                **{k: v for k, v in ep_inputs.items()
                   if k not in ("yoy_growth_pct", "qoq_direction", "gross_margin_trend",
                                "cash_and_st_investments", "quarterly_burn", "checklist_summary")
                   and isinstance(v, bool)},
                sources=["SEC EDGAR 10-Q"],
            )
        except Exception as e:
            logger.warning(f"earnings_profile scoring failed for {ticker}: {e}")

        # ── Step 4: Cash Runway ──────────────────────────────
        cash, burn = _extract_cash_inputs(deep_dive, ticker)
        try:
            factor_scores["cash_runway"] = score_cash_runway(
                cash_and_st_investments=cash,
                quarterly_burn=burn,
                sources=["SEC EDGAR 10-Q"],
            )
        except Exception as e:
            logger.warning(f"cash_runway scoring failed for {ticker}: {e}")

        # ── Step 5: News Quality ─────────────────────────────
        cal = FiscalCalendar.from_ticker_info(ticker, fiscal_year_end)
        news_inputs = {"current_quarter_news": [], "prior_quarter_news": [], "composition_shift": None}
        if earnings_date:
            try:
                current_fq, prior_fq = cal.get_quarters_until_earnings(earnings_date)
                news_inputs = tier_news_with_llm(ticker, company_name, current_fq, prior_fq)
            except Exception as e:
                logger.warning(f"News tiering failed for {ticker}: {e}")

        try:
            factor_scores["news_quality"] = score_news_quality(
                current_quarter_news=news_inputs.get("current_quarter_news", []),
                prior_quarter_news=news_inputs.get("prior_quarter_news", []),
                composition_shift=news_inputs.get("composition_shift"),
                sources=news_inputs.get("sources", []),
            )
        except Exception as e:
            logger.warning(f"news_quality scoring failed for {ticker}: {e}")

        # ── Step 6: Price Absorption Gap ────────────────────
        quarterly_chg = 0.0
        suppression_cause = "none_identified"
        try:
            quarterly_chg = get_quarterly_price_change(ticker) or 0.0
            share_struct = assess_share_structure(ticker, company_name, market_cap, earnings_date)
            suppression_cause = share_struct.get("suppression_cause", "none_identified")
        except Exception as e:
            logger.warning(f"share structure / price change fetch failed for {ticker}: {e}")

        news_qs = factor_scores.get("news_quality")
        try:
            factor_scores["price_absorption_gap"] = score_price_absorption(
                quarterly_price_change_pct=quarterly_chg,
                news_quality_score=news_qs.score if news_qs else 50,
                suppression_cause=suppression_cause,
                sources=["yfinance", "SEC EDGAR"],
            )
        except Exception as e:
            logger.warning(f"price_absorption scoring failed for {ticker}: {e}")

        # ── Step 7: Industry Momentum ────────────────────────
        try:
            industry_score = _get_industry_score(industry)
            factor_scores["industry_momentum"] = score_industry_momentum(
                industry_composite_score=industry_score,
                industry_name=industry or "unknown",
            )
        except Exception as e:
            logger.warning(f"industry_momentum scoring failed for {ticker}: {e}")

        # ── Step 8: Insider Activity (T-3 only) ──────────────
        if checkpoint == "T-3":
            try:
                factor_scores["insider_activity"] = _score_insider_activity(ticker)
            except Exception as e:
                logger.warning(f"insider_activity scoring failed for {ticker}: {e}")
        else:
            # Neutral placeholder for non-T-3 checkpoints
            try:
                factor_scores["insider_activity"] = score_insider_activity(
                    False, False, False, sources=["SEC EDGAR Form 4"]
                )
            except Exception as e:
                logger.warning(f"insider_activity placeholder failed for {ticker}: {e}")

        # ── Step 9: Options Flow (T-3 only) ──────────────────
        if checkpoint == "T-3":
            try:
                factor_scores["options_flow"] = _score_options_flow(ticker)
            except Exception as e:
                logger.warning(f"options_flow scoring failed for {ticker}: {e}")
        else:
            try:
                factor_scores["options_flow"] = score_options_flow(
                    1.0, 0.5, 50.0, 30.0, 1.0, 50.0, sources=["yfinance"]
                )
            except Exception as e:
                logger.warning(f"options_flow placeholder failed for {ticker}: {e}")

        # ── Step 10: MBP (T-21 only) ─────────────────────────
        if checkpoint == "T-21":
            try:
                mbp = generate_mbp(ticker, company_name, industry)
                includes_mbp = True
                key_findings.append(f"MBP generated: {mbp.agent_opinion[:100]}...")
            except Exception as e:
                logger.warning(f"MBP generation failed for {ticker}: {e}")

        # ── Step 11: Make Decision ────────────────────────────
        report = make_decision(
            ticker=ticker,
            checkpoint=checkpoint,
            factor_scores=factor_scores,
            prior_composite_score=prior_composite,
            hypothesis_direction=_infer_hypothesis(factor_scores),
            includes_mbp=includes_mbp,
        )
        report.key_findings = key_findings[:10]

        # ── Step 12: Save to DB ───────────────────────────────
        try:
            with get_db() as db:
                save_checkpoint(db, report)
        except Exception as e:
            logger.error(f"Failed to save checkpoint for {ticker}: {e}")

        # Update watchlist status
        try:
            if report.decision == "NO_GO":
                self.watchlist_mgr.mark_no_go(ticker)
            elif report.decision == "BUY" and checkpoint == "T-3":
                self.watchlist_mgr.mark_buy_alert(ticker)
            elif report.decision in ("BUY", "WATCH") and wl_status == "candidate":
                self.watchlist_mgr.promote_candidate(ticker)
        except Exception as e:
            logger.warning(f"Failed to update watchlist status for {ticker}: {e}")

        logger.info(f"{ticker} {checkpoint}: composite={report.composite_score}, decision={report.decision}")
        return report

    def run_final_call(self, ticker: str) -> FinalAlert:
        """
        Runs T-3 checkpoint and packages result as a FinalAlert.
        Human-in-the-loop: alert is saved but human confirms before acting.
        """
        report = self.run_checkpoint(ticker, "T-3")

        with get_db() as db:
            trajectory_data = get_trajectory(db, ticker)
        trajectory_scores = [score for _, score in trajectory_data]

        with get_db() as db:
            wl_row = get_by_ticker(db, ticker)
            wl_company_name = wl_row.company_name if wl_row else ticker
            wl_earnings_date = wl_row.earnings_date if wl_row else None

        options_fs = report.factor_scores.get("options_flow")
        insider_fs = report.factor_scores.get("insider_activity")

        _empty_fs = FactorScore(
            factor_name="", score=0, reasoning="", raw_inputs={}, sources=[],
            scored_at=datetime.now(timezone.utc)
        )

        alert = FinalAlert(
            ticker=ticker,
            company_name=wl_company_name,
            recommendation=report.decision,
            composite_score=report.composite_score,
            checkpoint_trajectory=trajectory_scores,
            core_news_score=report.factor_scores.get("news_quality", _empty_fs).score,
            core_pag_score=report.factor_scores.get("price_absorption_gap", _empty_fs).score,
            insider_summary=insider_fs.reasoning if insider_fs else "Not evaluated",
            options_snapshot=options_fs.reasoning if options_fs else "Not evaluated",
            share_structure_summary="\n".join(report.key_findings[:3]),
            thesis=_build_thesis(report, ticker),
            earnings_date=datetime.combine(wl_earnings_date, datetime.min.time()) if wl_earnings_date else datetime.now(timezone.utc),
            alert_sent_at=datetime.now(timezone.utc),
            hard_veto=report.hard_veto,
        )

        try:
            with get_db() as db:
                save_alert(db, alert)
        except Exception as e:
            logger.error(f"Failed to save alert for {ticker}: {e}")

        return alert


# ── Private helpers ───────────────────────────────────────────

def _extract_revenue_inputs(deep_dive: dict | None, ticker: str, eps_ttm: float | None) -> tuple[float, str, str]:
    """Returns (yoy_growth_pct, qoq_direction, gross_margin_trend)"""
    if not deep_dive:
        return 15.0, "flat", "stable"
    checklist = deep_dive.get("checklist", {})
    rev = checklist.get("revenue", {}).get("signal", "neutral")
    gm = checklist.get("gross_margin", {}).get("signal", "neutral")
    yoy = 15.0
    qoq = "positive" if rev == "bullish" else ("negative" if rev == "bearish" else "flat")
    gm_trend = "expanding" if gm == "bullish" else ("compressing" if gm == "bearish" else "stable")
    return yoy, qoq, gm_trend


def _extract_cash_inputs(deep_dive: dict | None, ticker: str) -> tuple[float, float]:
    """Returns (cash, quarterly_burn) — defaults to neutral if no data"""
    if not deep_dive:
        return 100_000_000.0, 20_000_000.0  # 5 quarters runway default
    checklist = deep_dive.get("checklist", {})
    cash_signal = checklist.get("cash", {}).get("signal", "neutral")
    if cash_signal == "bullish":
        return 200_000_000.0, 25_000_000.0   # ~8 quarters
    elif cash_signal == "bearish":
        return 50_000_000.0, 30_000_000.0    # ~1.7 quarters
    return 100_000_000.0, 20_000_000.0       # ~5 quarters


def _get_industry_score(industry: str | None) -> int:
    """Look up most recent industry composite score from DB"""
    if not industry:
        return 50
    with get_db() as db:
        from storage.repositories.industry_repo import get_latest_by_name
        row = get_latest_by_name(db, industry)
        return row.composite_score if row else 50


def _score_insider_activity(ticker: str) -> FactorScore:
    """Fetch Form 4 filings and score insider activity"""
    try:
        filings = get_form4_filings(ticker, days_back=30) or []
    except Exception:
        filings = []

    heavy_selling = False
    small_selling = False
    open_buys = False

    total_sell_value = 0.0
    for f in filings:
        ttype = str(f.get("transaction_type", "")).upper()
        shares = f.get("shares", 0) or 0
        price = f.get("price", 0) or 0
        value = shares * price
        if ttype in ("S", "SELL", "S-SALE"):
            total_sell_value += value
            small_selling = True
        elif ttype in ("P", "BUY", "PURCHASE"):
            open_buys = True

    if total_sell_value > 1_000_000:
        heavy_selling = True
        small_selling = False

    return score_insider_activity(
        open_market_buys_detected=open_buys,
        heavy_discretionary_selling=heavy_selling,
        small_discretionary_selling=small_selling and not open_buys,
        sources=["SEC EDGAR Form 4"],
    )


def _score_options_flow(ticker: str) -> FactorScore:
    """Fetch options metrics and score"""
    provider = get_options_provider()
    metrics = provider.get_metrics(ticker) or {}
    return score_options_flow(
        call_sizzle_index=metrics.get("call_sizzle_index", 1.0),
        put_sizzle_index=metrics.get("put_sizzle_index", 0.5),
        volume_at_ask_pct=metrics.get("volume_at_ask_pct", 50.0),
        volume_at_bid_pct=metrics.get("volume_at_bid_pct", 30.0),
        call_put_ratio=metrics.get("call_put_ratio", 1.0),
        iv_percentile=metrics.get("iv_percentile", 50.0),
        sources=[f"options:{provider.provider_name}"],
    )


def _infer_hypothesis(factor_scores: dict[str, FactorScore]) -> str:
    news = factor_scores.get("news_quality")
    pag = factor_scores.get("price_absorption_gap")
    if news and pag:
        core_avg = (news.score + pag.score) / 2
        if core_avg >= 65:
            return "bullish"
        elif core_avg < 45:
            return "bearish"
    return "neutral"


def _build_thesis(report: CheckpointReport, ticker: str) -> str:
    news_fs = report.factor_scores.get("news_quality")
    pag_fs = report.factor_scores.get("price_absorption_gap")
    rev_fs = report.factor_scores.get("revenue_trend")

    if report.hard_veto:
        return f"{ticker} issued NO-GO due to heavy insider selling. Hard veto overrides all other factors."

    direction = "bullish" if report.composite_score >= 70 else ("bearish" if report.composite_score < 50 else "mixed")
    news_txt = f"News quality scored {news_fs.score}/100" if news_fs else "News data limited"
    pag_txt = f"price absorption gap at {pag_fs.score}/100" if pag_fs else ""
    rev_txt = f"revenue trend scored {rev_fs.score}/100" if rev_fs else ""

    parts = [p for p in [news_txt, pag_txt, rev_txt] if p]
    return f"{ticker} shows {direction} setup heading into earnings. {', '.join(parts)}. Composite score: {report.composite_score}/100."
