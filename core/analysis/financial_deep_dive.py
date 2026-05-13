import json
from datetime import datetime
from models.scores import FactorScore
from utils.llm import get_llm_client
from utils.prompts import FINANCIAL_DEEP_DIVE_SYSTEM, FINANCIAL_DEEP_DIVE_USER
from utils.logger import logger
from data.edgar_client import get_recent_filings, get_filing_text, get_cik


def run_financial_deep_dive(
    ticker: str,
    company_name: str,
    eps_ttm: float | None,
    sources: list[str] = [],
) -> dict:
    """
    Fetches the most recent 10-Q (or 10-K if no 10-Q found), runs LLM analysis
    against the 13-item checklist, returns structured findings.

    Returns:
    {
        "checklist": {
            "revenue": {"finding": str, "signal": "bullish|bearish|neutral", "evidence": str},
            ... 13 items ...
        },
        "overall_assessment": "bullish|bearish|neutral",
        "key_risks": list[str],
        "key_strengths": list[str],
        "filing_type": str,
        "filing_period": str,
        "filing_url": str | None,
        "raw_llm_response": str,
        "error": str | None,
    }
    """
    # 1. Get CIK and most recent 10-Q
    cik = get_cik(ticker)
    filing_text = None
    filing_type = None
    filing_period = None
    filing_url = None

    for form in ["10-Q", "10-K"]:
        filings = get_recent_filings(ticker, form, count=1)
        if filings:
            f = filings[0]
            filing_type = form
            filing_period = f.get("filing_date", "unknown")
            filing_url = f.get("document_url")
            # Try to get filing text
            acc = f.get("accession_number", "")
            if acc and cik:
                logger.info(f"financial_deep_dive [{ticker}]: fetching {form} {acc[:20]}...")
                filing_text = get_filing_text(acc, cik)
            if filing_text:
                break

    if not filing_text:
        logger.warning(f"No filing text found for {ticker} — returning empty deep dive")
        return {
            "checklist": {},
            "overall_assessment": "neutral",
            "key_risks": [],
            "key_strengths": [],
            "filing_type": filing_type or "unknown",
            "filing_period": filing_period or "unknown",
            "filing_url": filing_url,
            "raw_llm_response": "",
            "error": "No filing text available",
        }

    # 2. Truncate filing text — keep first 40,000 chars (LLM context limit)
    filing_text_truncated = filing_text[:40000]
    if len(filing_text) > 40000:
        logger.info(f"Filing text truncated from {len(filing_text)} to 40,000 chars for {ticker}")

    # 3. Build prompt
    user_msg = FINANCIAL_DEEP_DIVE_USER.format(
        company_name=company_name,
        ticker=ticker,
        filing_type=filing_type,
        period=filing_period,
        eps_ttm=eps_ttm if eps_ttm is not None else "unknown",
        filing_text=filing_text_truncated,
    )

    # 4. Call LLM — use Sonnet (this is a heavy analysis task)
    client = get_llm_client()
    raw_response = ""
    try:
        raw_response = client.complete(
            system_prompt=FINANCIAL_DEEP_DIVE_SYSTEM,
            user_message=user_msg,
            operation_name=f"financial_deep_dive_{ticker}",
            max_tokens=4096,
        )
        logger.info(f"financial_deep_dive [{ticker}]: LLM response received ({len(raw_response)} chars)")
        clean = raw_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
        error = None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON for {ticker}: {e}")
        result = {"checklist": {}, "overall_assessment": "neutral", "key_risks": [], "key_strengths": []}
        error = f"JSON parse error: {e}"
    except Exception as e:
        logger.error(f"LLM call failed for {ticker} financial deep dive: {e}")
        result = {"checklist": {}, "overall_assessment": "neutral", "key_risks": [], "key_strengths": []}
        error = str(e)

    return {
        "checklist": result.get("checklist", {}),
        "overall_assessment": result.get("overall_assessment", "neutral"),
        "key_risks": result.get("key_risks", []),
        "key_strengths": result.get("key_strengths", []),
        "filing_type": filing_type or "unknown",
        "filing_period": filing_period or "unknown",
        "filing_url": filing_url,
        "raw_llm_response": raw_response,
        "error": error,
    }


def extract_financial_inputs_for_scoring(deep_dive: dict) -> dict:
    """
    Maps the LLM checklist output to concrete bool/float inputs for the scoring functions.

    Mapping assumption: LLM-assigned signal ("bullish"/"bearish"/"neutral") for each
    checklist item is converted to boolean flags. This is intentional — the LLM acts as
    a structured-signal extractor, and downstream scorers consume the booleans directly.
    A "bullish" signal on "opex" means R&D spending is healthy; "bearish" means SGA is
    rising faster than revenue. Callers should provide actual numeric values (yoy_growth_pct,
    cash_and_st_investments, quarterly_burn) from yfinance when available, as the LLM
    does not return raw numbers.

    Returns a dict ready to splat into the various scorers:
    {
        # For revenue_trend scorer:
        "yoy_growth_pct": float | None,
        "qoq_direction": "positive"|"flat"|"negative"|None,
        "gross_margin_trend": "expanding"|"stable"|"compressing"|None,

        # For cash_runway scorer:
        "cash_and_st_investments": float | None,
        "quarterly_burn": float | None,

        # For earnings_profile scorer — Track A booleans:
        "rd_increasing_gt10_pct": bool,
        "capex_rising": bool,
        "new_products_or_expansion": bool,
        "deferred_revenue_increasing": bool,
        "mgmt_framing_losses_as_investment": bool,
        "revenue_declining_while_losses_widen": bool,
        "sga_rising_faster_than_revenue": bool,
        "customer_churn_in_filings": bool,
        "no_new_product_pipeline": bool,
        "mgmt_guidance_vague_or_declining": bool,

        # For earnings_profile scorer — Track B booleans:
        "gross_margins_expanding_2q": bool,
        "opex_less_than_revenue_growth": bool,
        "eps_growth_accelerating": bool,
        "revenue_gt15_stable_margins": bool,
        "consensus_eps_below_run_rate": bool,
        "gross_margins_declining_2q": bool,
        "sga_cogs_growing_faster": bool,
        "eps_growth_decelerating": bool,
        "consensus_eps_above_trajectory": bool,
        "mgmt_lowering_margin_guidance": bool,

        "checklist_summary": str,   # plain English summary for reasoning
    }
    """
    checklist = deep_dive.get("checklist", {})

    def signal(key: str) -> str:
        item = checklist.get(key, {})
        return item.get("signal", "neutral")

    def is_bullish(key: str) -> bool:
        return signal(key) == "bullish"

    def is_bearish(key: str) -> bool:
        return signal(key) == "bearish"

    # Revenue
    yoy_growth_pct = None  # LLM doesn't give exact numbers — caller must provide from yfinance
    qoq_direction = (
        "positive" if is_bullish("revenue") else ("negative" if is_bearish("revenue") else "flat")
    )
    gross_margin_trend = (
        "expanding"
        if is_bullish("gross_margin")
        else ("compressing" if is_bearish("gross_margin") else "stable")
    )

    # Cash (LLM flags signal, caller provides actual numbers)
    cash_and_st_investments = None
    quarterly_burn = None

    # Checklist summary for reasoning
    summary_lines = []
    for key, label in [
        ("revenue", "Revenue"),
        ("gross_margin", "Gross Margin"),
        ("opex", "OpEx"),
        ("cash", "Cash Runway"),
        ("deferred_revenue", "Deferred Revenue"),
        ("customer_concentration", "Customer Concentration"),
        ("eps", "EPS vs Consensus"),
        ("guidance", "Mgmt Guidance"),
        ("fcf", "Free Cash Flow"),
        ("debt_maturity", "Debt Maturity"),
        ("profitability_trajectory", "Profitability"),
        ("margin_expansion", "Margin Expansion"),
        ("share_structure", "Share Structure"),
    ]:
        item = checklist.get(key, {})
        if item:
            summary_lines.append(
                f"{label}: {item.get('signal', 'N/A')} — {item.get('finding', '')[:100]}"
            )

    return {
        "yoy_growth_pct": yoy_growth_pct,
        "qoq_direction": qoq_direction,
        "gross_margin_trend": gross_margin_trend,
        "cash_and_st_investments": cash_and_st_investments,
        "quarterly_burn": quarterly_burn,
        # Track A
        "rd_increasing_gt10_pct": is_bullish("opex"),
        "capex_rising": is_bullish("profitability_trajectory"),
        "new_products_or_expansion": is_bullish("deferred_revenue"),
        "deferred_revenue_increasing": is_bullish("deferred_revenue"),
        "mgmt_framing_losses_as_investment": is_bullish("guidance"),
        "revenue_declining_while_losses_widen": is_bearish("revenue"),
        "sga_rising_faster_than_revenue": is_bearish("opex"),
        "customer_churn_in_filings": is_bearish("customer_concentration"),
        "no_new_product_pipeline": is_bearish("deferred_revenue"),
        "mgmt_guidance_vague_or_declining": is_bearish("guidance"),
        # Track B
        "gross_margins_expanding_2q": is_bullish("gross_margin"),
        "opex_less_than_revenue_growth": is_bullish("opex"),
        "eps_growth_accelerating": is_bullish("eps"),
        "revenue_gt15_stable_margins": is_bullish("revenue"),
        "consensus_eps_below_run_rate": is_bullish("eps"),
        "gross_margins_declining_2q": is_bearish("gross_margin"),
        "sga_cogs_growing_faster": is_bearish("opex"),
        "eps_growth_decelerating": is_bearish("eps"),
        "consensus_eps_above_trajectory": is_bearish("eps"),
        "mgmt_lowering_margin_guidance": is_bearish("guidance"),
        "checklist_summary": "\n".join(summary_lines),
    }
