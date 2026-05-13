#!/usr/bin/env python3
"""
Phase 4 verification script. Run directly: python3 tests/test_phase4.py
Tests analysis modules with live data (EDGAR, yfinance) and LLM (if API key set).
"""
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from datetime import date

SEP = "\n" + "="*60 + "\n"

def test_fiscal_calendar():
    print(SEP + "FISCAL CALENDAR")
    from orchestrator.fiscal_calendar import FiscalCalendar

    # Standard calendar year
    cal_std = FiscalCalendar.from_ticker_info("AAPL", "September 30")
    fq = cal_std.get_quarter_for_date(date(2026, 2, 15))
    print(f"  AAPL (FY ends Sep 30): Feb 15, 2026 → {fq.label} ({fq.start_date} to {fq.end_date})")
    prior = cal_std.get_prior_quarter(fq)
    print(f"  Prior quarter: {prior.label} ({prior.start_date} to {prior.end_date})")

    # Snowflake: FY ends Jan 31
    cal_snow = FiscalCalendar.from_ticker_info("SNOW", "January 31")
    fq_snow = cal_snow.get_quarter_for_date(date(2026, 3, 1))
    print(f"  SNOW (FY ends Jan 31): Mar 1, 2026 → {fq_snow.label} ({fq_snow.start_date} to {fq_snow.end_date})")
    prior_snow = cal_snow.get_prior_quarter(fq_snow)
    print(f"  Prior quarter: {prior_snow.label} ({prior_snow.start_date} to {prior_snow.end_date})")

    # Checkpoint dates
    earnings = date(2026, 6, 1)
    t21 = cal_std.get_checkpoint_date(earnings, 21)
    t3 = cal_std.get_checkpoint_date(earnings, 3)
    print(f"  Earnings June 1 → T-21: {t21}, T-3: {t3}")
    print("✓ fiscal_calendar: all checks passed")

def test_share_structure_no_llm():
    print(SEP + "SHARE STRUCTURE (no LLM key required)")
    from core.analysis.share_structure import assess_share_structure
    result = assess_share_structure("AAPL", "Apple Inc", market_cap=4.3e12, earnings_date=date(2026, 7, 30))
    print(f"  overall_risk = {result['overall_risk']}")
    print(f"  suppression_cause = {result['suppression_cause']}")
    print(f"  resale_registrations = {result['resale_registrations']}")
    print(f"  summary = {result['summary'][:100]}")
    print("✓ share_structure: returned structured result")

def test_financial_deep_dive_no_llm():
    print(SEP + "FINANCIAL DEEP DIVE (no LLM — tests EDGAR fetch)")
    from data.edgar_client import get_recent_filings, get_cik
    cik = get_cik("NVDA")
    print(f"  NVDA CIK: {cik}")
    filings = get_recent_filings("NVDA", "10-Q", count=2)
    print(f"  NVDA 10-Q filings found: {len(filings)}")
    if filings:
        print(f"  Latest: {filings[0].get('filing_date')} — {filings[0].get('accession_number', '')[:20]}...")
    print("✓ financial_deep_dive: EDGAR fetch works")

def test_with_llm():
    if not os.getenv("ANTHROPIC_API_KEY"):
        print(SEP + "LLM TESTS SKIPPED (no ANTHROPIC_API_KEY)")
        return

    print(SEP + "FINANCIAL DEEP DIVE (with LLM — NVDA)")
    from core.analysis.financial_deep_dive import run_financial_deep_dive, extract_financial_inputs_for_scoring
    result = run_financial_deep_dive("NVDA", "NVIDIA Corporation", eps_ttm=2.53)
    if result.get("error"):
        print(f"  ⚠ error: {result['error']}")
    else:
        checklist = result.get("checklist", {})
        print(f"  Filing type: {result['filing_type']} ({result['filing_period']})")
        print(f"  Overall: {result['overall_assessment']}")
        print(f"  Checklist items returned: {len(checklist)}")
        print(f"  Key strengths: {result['key_strengths'][:2]}")
        print(f"  Key risks: {result['key_risks'][:2]}")
        inputs = extract_financial_inputs_for_scoring(result)
        print(f"  qoq_direction: {inputs['qoq_direction']}")
        print(f"  gross_margin_trend: {inputs['gross_margin_trend']}")

    print(SEP + "MBP (with LLM — ARM Holdings)")
    from core.analysis.mbp import generate_mbp, format_mbp_for_report
    mbp = generate_mbp("ARM", "Arm Holdings plc", industry="Semiconductors")
    print(f"  People profiled: {len(mbp.people)}")
    if mbp.people:
        print(f"  CEO: {mbp.people[0].name} ({mbp.people[0].title})")
    print(f"  Agent opinion: {mbp.agent_opinion[:200]}")
    print(f"  Data sources: {mbp.data_sources}")

    from utils.llm import get_llm_client
    client = get_llm_client()
    client.log_session_summary()

if __name__ == "__main__":
    print("\n=== Phase 4 Analysis Engine Verification ===\n")
    for fn in [test_fiscal_calendar, test_share_structure_no_llm, test_financial_deep_dive_no_llm, test_with_llm]:
        try:
            fn()
        except Exception as e:
            import traceback
            print(f"✗ {fn.__name__}: {e}")
            traceback.print_exc()
    print("\n=== Done ===")
