"""Wrapper around sec_edgar_downloader for fetching SEC filings.

SEC EDGAR policy requires a real User-Agent (Name email). Requests with default
or missing user agents are blocked. Configure via SEC_USER_AGENT in .env.
"""

from __future__ import annotations

from pathlib import Path

from sec_edgar_downloader import Downloader  # type: ignore

import config


def get_downloader() -> Downloader:
    """Build a sec_edgar_downloader.Downloader using the configured User-Agent."""
    ua = config.SEC_USER_AGENT or "AskYour10K research@example.com"
    parts = ua.split(maxsplit=1)
    company_name = parts[0] if parts else "AskYour10K"
    email = parts[1] if len(parts) > 1 else "research@example.com"
    return Downloader(company_name, email, download_folder=str(config.DATA_DIR))


def download_filing(ticker: str, form_type: str, fiscal_year: int | None = None) -> list[Path]:
    """Download filings of the given form type for a ticker.

    Passes download_details=True so sec_edgar_downloader also fetches the primary
    HTML document (not just the raw full-submission.txt SGML blob), since parsers.py
    expects real HTML. Returns the list of downloaded file paths.
    """
    dl = get_downloader()
    dl.get(
        form_type,
        ticker,
        after=f"{fiscal_year}-01-01" if fiscal_year else None,
        download_details=True,
    )

    # Real v5 layout: DATA_DIR/sec-edgar-filings/<ticker>/<form_type>/<accession>/
    filing_dir = config.DATA_DIR / "sec-edgar-filings" / ticker / form_type
    if not filing_dir.exists():
        return []
    return sorted(filing_dir.rglob("*"))
