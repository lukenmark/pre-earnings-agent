import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from data.cache import get, set, make_key
from utils.logger import logger

EDGAR_BASE = "https://data.sec.gov"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

HEADERS = {"User-Agent": "pre-earnings-agent research@example.com"}

_company_tickers_cache: dict | None = None


def _sleep():
    time.sleep(0.1)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=False)
def _get(url: str, params: dict | None = None) -> requests.Response | None:
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp


def _load_company_tickers() -> dict:
    global _company_tickers_cache
    if _company_tickers_cache is not None:
        return _company_tickers_cache
    cached = get(make_key("filings", "company_tickers"))
    if cached:
        _company_tickers_cache = cached
        return cached
    try:
        resp = _get(COMPANY_TICKERS_URL)
        _sleep()
        if resp is None:
            return {}
        data = resp.json()
        # Build ticker -> cik mapping
        ticker_map = {}
        for entry in data.values():
            t = entry.get("ticker", "").upper()
            cik = str(entry.get("cik_str", "")).zfill(10)
            if t:
                ticker_map[t] = cik
        set(make_key("filings", "company_tickers"), ticker_map, "filings")
        _company_tickers_cache = ticker_map
        return ticker_map
    except Exception as e:
        logger.warning(f"_load_company_tickers: {e}")
        return {}


def get_cik(ticker: str) -> str | None:
    """Look up CIK number for a ticker"""
    key = make_key("filings", ticker, "cik")
    cached = get(key)
    if cached is not None:
        return cached
    try:
        ticker_map = _load_company_tickers()
        cik = ticker_map.get(ticker.upper())
        if cik:
            set(key, cik, "filings")
            return cik
        logger.warning(f"get_cik: no CIK found for {ticker}")
        return None
    except Exception as e:
        logger.warning(f"get_cik({ticker}): {e}")
        return None


def get_recent_filings(ticker: str, form_type: str, count: int = 5) -> list[dict]:
    """Returns list of recent filings metadata"""
    key = make_key("filings", ticker, form_type)
    cached = get(key)
    if cached is not None:
        return cached

    cik = get_cik(ticker)
    if not cik:
        logger.warning(f"get_recent_filings: no CIK for {ticker}")
        return []

    try:
        _sleep()
        resp = _get(
            f"{EDGAR_SUBMISSIONS}/CIK{cik}.json",
        )
        if resp is None:
            return []
        data = resp.json()
        filings_data = data.get("filings", {}).get("recent", {})
        form_types = filings_data.get("form", [])
        dates = filings_data.get("filingDate", [])
        accessions = filings_data.get("accessionNumber", [])
        primary_docs = filings_data.get("primaryDocument", [])

        results = []
        for i, ft in enumerate(form_types):
            if ft == form_type:
                acc = accessions[i] if i < len(accessions) else ""
                acc_nodash = acc.replace("-", "")
                doc = primary_docs[i] if i < len(primary_docs) else ""
                doc_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{doc}"
                    if acc_nodash and doc
                    else None
                )
                results.append(
                    {
                        "accession_number": acc,
                        "filing_date": dates[i] if i < len(dates) else None,
                        "form_type": ft,
                        "document_url": doc_url,
                        "cik": cik,
                    }
                )
                if len(results) >= count:
                    break

        set(key, results, "filings")
        return results
    except Exception as e:
        logger.warning(f"get_recent_filings({ticker}, {form_type}): {e}")
        return []


def get_filing_text(accession_number: str, cik: str) -> str | None:
    """Download and return the text content of a filing (first 50k chars)"""
    key = make_key("filings", accession_number)
    cached = get(key)
    if cached is not None:
        return cached

    try:
        cik_int = int(cik)
        acc_nodash = accession_number.replace("-", "")
        # Fetch the filing index to find the primary document
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{accession_number}-index.htm"
        _sleep()
        resp = _get(index_url)
        if resp is None:
            return None

        # Try to parse out a .htm/.txt document link from the index
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        doc_link = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".htm") or href.endswith(".html") or href.endswith(".txt"):
                if "index" not in href.lower():
                    doc_link = href
                    break

        if not doc_link:
            logger.warning(f"get_filing_text: no doc link found for {accession_number}")
            return None

        if not doc_link.startswith("http"):
            doc_link = f"https://www.sec.gov{doc_link}"

        _sleep()
        doc_resp = _get(doc_link)
        if doc_resp is None:
            return None

        text = doc_resp.text[:50000]
        set(key, text, "filings")
        return text
    except Exception as e:
        logger.warning(f"get_filing_text({accession_number}): {e}")
        return None


def get_form4_filings(ticker: str, days_back: int = 30) -> list[dict]:
    """Returns recent Form 4 filings (insider transactions)"""
    key = make_key("filings", ticker, "form4")
    cached = get(key)
    if cached is not None:
        return cached

    cik = get_cik(ticker)
    if not cik:
        return []

    try:
        _sleep()
        resp = _get(
            f"{EDGAR_SUBMISSIONS}/CIK{cik}.json",
        )
        if resp is None:
            return []
        data = resp.json()
        filings_data = data.get("filings", {}).get("recent", {})
        form_types = filings_data.get("form", [])
        dates = filings_data.get("filingDate", [])
        accessions = filings_data.get("accessionNumber", [])

        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        results = []
        for i, ft in enumerate(form_types):
            if ft == "4":
                filing_date = dates[i] if i < len(dates) else ""
                if filing_date < cutoff:
                    continue
                results.append(
                    {
                        "transaction_date": filing_date,
                        "accession_number": accessions[i] if i < len(accessions) else "",
                        "form_type": "4",
                        "cik": cik,
                    }
                )

        set(key, results, "filings")
        return results
    except Exception as e:
        logger.warning(f"get_form4_filings({ticker}): {e}")
        return []


def get_shelf_registrations(ticker: str) -> list[dict]:
    """Returns recent S-3 and 424B filings (dilution signals)"""
    key = make_key("filings", ticker, "shelf")
    cached = get(key)
    if cached is not None:
        return cached

    target_forms = {"S-3", "S-3/A", "424B4", "424B7", "424B3"}
    cik = get_cik(ticker)
    if not cik:
        return []

    try:
        _sleep()
        resp = _get(f"{EDGAR_SUBMISSIONS}/CIK{cik}.json")
        if resp is None:
            return []
        data = resp.json()
        filings_data = data.get("filings", {}).get("recent", {})
        form_types = filings_data.get("form", [])
        dates = filings_data.get("filingDate", [])
        descriptions = filings_data.get("primaryDocDescription", [])

        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        results = []
        for i, ft in enumerate(form_types):
            if ft in target_forms:
                filing_date = dates[i] if i < len(dates) else ""
                if filing_date < cutoff:
                    continue
                results.append(
                    {
                        "filing_date": filing_date,
                        "form_type": ft,
                        "description": descriptions[i] if i < len(descriptions) else "",
                        "cik": cik,
                    }
                )

        set(key, results, "filings")
        return results
    except Exception as e:
        logger.warning(f"get_shelf_registrations({ticker}): {e}")
        return []
