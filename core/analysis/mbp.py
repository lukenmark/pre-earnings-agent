import json
from datetime import datetime, timezone
from models.mbp import ManagementBackgroundProfile, MBPPerson
from utils.llm import get_llm_client
from utils.prompts import MBP_SYSTEM, MBP_USER
from utils.logger import logger
from data.edgar_client import get_recent_filings, get_filing_text, get_cik


def generate_mbp(
    ticker: str,
    company_name: str,
    industry: str | None = None,
    sources: list[str] = [],
) -> ManagementBackgroundProfile:
    """
    Generates the Management Background Profile for the T-21 checkpoint.

    Uses the DEF 14A (proxy statement) as primary source for management info.
    Falls back to 10-K if no proxy statement available.

    Note: This costs ~$0.01-0.03 per call (Sonnet, ~3k-5k input tokens).
    MBP is generated once at T-21 and not repeated unless C-suite changes.
    """
    # 1. Fetch proxy statement (DEF 14A) — contains executive bios and compensation
    cik = get_cik(ticker)
    proxy_text = ""
    additional_context = ""
    proxy_filings = []

    logger.info(f"mbp [{ticker}]: starting MBP generation, cik={cik}")

    proxy_filings = get_recent_filings(ticker, "DEF 14A", count=1)
    if proxy_filings and cik:
        acc = proxy_filings[0].get("accession_number", "")
        if acc:
            logger.info(f"mbp [{ticker}]: fetching DEF 14A {acc[:20]}...")
            text = get_filing_text(acc, cik)
            if text:
                proxy_text = text[:30000]  # proxy statements can be huge — cap

    # 2. Fallback: use 10-K which includes management section
    if not proxy_text:
        annual_filings = get_recent_filings(ticker, "10-K", count=1)
        if annual_filings and cik:
            acc = annual_filings[0].get("accession_number", "")
            if acc:
                logger.info(f"mbp [{ticker}]: no proxy found, falling back to 10-K {acc[:20]}...")
                text = get_filing_text(acc, cik)
                if text:
                    proxy_text = f"[From 10-K — no proxy statement found]\n{text[:25000]}"
                    additional_context = (
                        "Note: Using 10-K executive section as proxy statement was unavailable."
                    )

    if not proxy_text:
        logger.warning(f"No proxy statement or 10-K found for {ticker} — generating minimal MBP")
        proxy_text = f"No proxy statement or 10-K available for {company_name} ({ticker})."
        additional_context = (
            "Filing data unavailable — profile is based on LLM general knowledge only."
        )

    # 3. Build LLM prompt
    user_msg = MBP_USER.format(
        company_name=company_name,
        ticker=ticker,
        industry=industry or "unknown",
        proxy_text=proxy_text,
        additional_context=additional_context,
    )

    # 4. Call LLM — use Sonnet for quality (MBP is human-reviewed)
    client = get_llm_client()
    try:
        raw_response = client.complete(
            system_prompt=MBP_SYSTEM,
            user_message=user_msg,
            operation_name=f"mbp_{ticker}",
            max_tokens=4096,
        )
        logger.info(f"mbp [{ticker}]: LLM response received ({len(raw_response)} chars)")
        clean = raw_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
    except json.JSONDecodeError as e:
        logger.error(f"MBP JSON parse failed for {ticker}: {e}")
        result = _empty_mbp_result(ticker, company_name)
    except Exception as e:
        logger.error(f"MBP LLM call failed for {ticker}: {e}")
        result = _empty_mbp_result(ticker, company_name)

    # 5. Build ManagementBackgroundProfile model
    people = []
    for p in result.get("people", []):
        try:
            people.append(
                MBPPerson(
                    name=p.get("name", "Unknown"),
                    title=p.get("title", "Unknown"),
                    career_history=p.get("career_history", ""),
                    prior_company_outcomes=p.get("prior_company_outcomes", ""),
                    sec_enforcement_issues=p.get("sec_enforcement_issues", "None identified"),
                    other_board_seats=p.get("other_board_seats", []),
                    ownership_stake=p.get("ownership_stake", "Unknown"),
                )
            )
        except Exception as e:
            logger.warning(f"Failed to parse MBP person for {ticker}: {e}")

    all_sources = list(
        set(
            sources
            + [
                "SEC EDGAR DEF 14A" if proxy_filings else "SEC EDGAR 10-K",
                "sec.gov",
            ]
        )
    )

    return ManagementBackgroundProfile(
        ticker=ticker,
        people=people,
        corporate_lineage=result.get("corporate_lineage", ""),
        related_party_transactions=result.get("related_party_transactions", ""),
        capital_markets_behavior=result.get("capital_markets_behavior", ""),
        auditor_history=result.get("auditor_history", ""),
        agent_opinion=result.get("agent_opinion", "Insufficient data to form opinion."),
        generated_at=datetime.now(timezone.utc),
        data_sources=all_sources,
    )


def _empty_mbp_result(ticker: str, company_name: str) -> dict:
    return {
        "people": [],
        "corporate_lineage": f"Could not retrieve data for {company_name} ({ticker})",
        "related_party_transactions": "Analysis unavailable",
        "capital_markets_behavior": "Analysis unavailable",
        "auditor_history": "Analysis unavailable",
        "agent_opinion": (
            "MBP generation failed — insufficient data. Manual review recommended."
        ),
    }


def format_mbp_for_report(mbp: ManagementBackgroundProfile) -> str:
    """Formats MBP as plain text for inclusion in checkpoint report"""
    lines = [
        f"=== MANAGEMENT BACKGROUND PROFILE: {mbp.ticker} ===",
        f"Generated: {mbp.generated_at.strftime('%Y-%m-%d')}",
        "",
        "CORPORATE LINEAGE:",
        mbp.corporate_lineage,
        "",
        "RELATED-PARTY TRANSACTIONS:",
        mbp.related_party_transactions,
        "",
        "CAPITAL MARKETS BEHAVIOR:",
        mbp.capital_markets_behavior,
        "",
        "AUDITOR HISTORY:",
        mbp.auditor_history,
        "",
    ]

    for person in mbp.people:
        lines += [
            f"--- {person.title}: {person.name} ---",
            f"Career: {person.career_history}",
            f"Prior Company Outcomes: {person.prior_company_outcomes}",
            f"SEC/Regulatory Issues: {person.sec_enforcement_issues}",
            f"Other Board Seats: {', '.join(person.other_board_seats) or 'None'}",
            f"Ownership Stake: {person.ownership_stake}",
            "",
        ]

    lines += [
        "AGENT OPINION (qualitative — for human review):",
        mbp.agent_opinion,
        "",
        "DATA SOURCES:",
        ", ".join(mbp.data_sources),
        "",
        "NOTE: MBP does not feed into the composite score. Human review required.",
    ]

    return "\n".join(lines)
