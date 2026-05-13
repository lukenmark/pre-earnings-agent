import json
from datetime import date, timedelta
from models.scores import FactorScore
from utils.llm import get_llm_client
from utils.prompts import SHARE_STRUCTURE_SYSTEM, SHARE_STRUCTURE_USER
from utils.logger import logger
from data.edgar_client import get_shelf_registrations, get_recent_filings, get_filing_text, get_cik
from utils.formatting import format_currency


def assess_share_structure(
    ticker: str,
    company_name: str,
    market_cap: float | None,
    earnings_date: date | None,
    sources: list[str] = [],
) -> dict:
    """
    Analyzes share structure risk from SEC filings.

    Returns:
    {
        "recent_offerings": {"detected": bool, "details": str},
        "warrant_overhang": {"detected": bool, "pct_of_float": float|None, "details": str},
        "resale_registrations": {"detected": bool, "count": int, "details": str},
        "lockup_expiration": {"detected": bool, "expiry_date": str|None, "details": str},
        "share_count_increase": {"detected": bool, "qoq_pct": float|None, "details": str},
        "overall_risk": "low|medium|high",
        "suppression_cause": "mechanical|none_identified|not_suppressed",
        "summary": str,
        "sources": list[str],
    }
    """
    # 1. Fetch relevant filings
    shelf_filings = get_shelf_registrations(ticker)
    cik = get_cik(ticker)

    logger.info(
        f"share_structure [{ticker}]: {len(shelf_filings)} shelf filings found, cik={cik}"
    )

    # Get latest 10-Q for share count
    filings_text_parts = []

    if shelf_filings:
        filings_text_parts.append(f"SHELF/RESALE REGISTRATIONS ({len(shelf_filings)} found):")
        for f in shelf_filings[:5]:
            filings_text_parts.append(
                f"  - {f.get('filing_date', '')}: {f.get('form_type', '')} — {f.get('description', '')}"
            )

    recent_10q = get_recent_filings(ticker, "10-Q", count=2)
    for f in recent_10q[:1]:
        acc = f.get("accession_number", "")
        if acc and cik:
            text = get_filing_text(acc, cik)
            if text:
                # Extract just the shares outstanding section (first 5000 chars has cover page)
                filings_text_parts.append(
                    f"\n10-Q EXCERPT ({f.get('filing_date', '')}):\n{text[:5000]}"
                )

    filings_text = "\n".join(filings_text_parts) if filings_text_parts else "No filing data available."

    # 2. Build LLM prompt
    user_msg = SHARE_STRUCTURE_USER.format(
        company_name=company_name,
        ticker=ticker,
        market_cap=format_currency(market_cap) if market_cap else "unknown",
        earnings_date=earnings_date.isoformat() if earnings_date else "unknown",
        filings_text=filings_text[:8000],  # cap at 8k chars
    )

    client = get_llm_client()
    try:
        raw_response = client.complete(
            system_prompt=SHARE_STRUCTURE_SYSTEM,
            user_message=user_msg,
            operation_name=f"share_structure_{ticker}",
            use_haiku=True,  # simpler task — Haiku is fine
            max_tokens=1024,
        )
        logger.debug(f"share_structure [{ticker}]: LLM response received")
        clean = raw_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
    except Exception as e:
        logger.warning(f"Share structure LLM failed for {ticker}: {e}")
        result = {
            "recent_offerings": {"detected": False, "details": "Analysis unavailable"},
            "warrant_overhang": {
                "detected": False,
                "pct_of_float": None,
                "details": "Analysis unavailable",
            },
            "resale_registrations": {
                "detected": len(shelf_filings) > 0,
                "count": len(shelf_filings),
                "details": f"{len(shelf_filings)} shelf filings found",
            },
            "lockup_expiration": {
                "detected": False,
                "expiry_date": None,
                "details": "Analysis unavailable",
            },
            "share_count_increase": {
                "detected": False,
                "qoq_pct": None,
                "details": "Analysis unavailable",
            },
            "overall_risk": "medium" if shelf_filings else "low",
            "suppression_cause": "mechanical" if shelf_filings else "none_identified",
            "summary": f"Found {len(shelf_filings)} shelf registrations. Full analysis unavailable.",
        }

    result["sources"] = list(set(sources + ["SEC EDGAR", "sec.gov/submissions"]))
    return result
