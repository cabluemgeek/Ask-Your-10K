"""Wrapper around sec_edgar_downloader for fetching SEC filings.

SEC EDGAR policy requires a real User-Agent (Name email). Requests with default
or missing user agents are blocked. Configure via SEC_USER_AGENT in .env.
"""

from __future__ import annotations

from pathlib import Path

from sec_edgar_downloader import Downloader

import config


def get_downloader() -> Downloader:
    """Build a sec_edgar_downloader.Downloader using the configured User-Agent."""
    # Split "Name email" into the two args Downloader expects.
    # Fallback to safe defaults if the env var is misconfigured.
    ua = config.SEC_USER_AGENT or "AskYour10K research@example.com"
    parts = ua.split(maxsplit=1)
    company_name = parts[0] if parts else "AskYour10K"
    email = parts[1] if len(parts) > 1 else "research@example.com"
    return Downloader(company_name, email, download_folder=str(config.DATA_DIR))


def download_filing(ticker: str, form_type: str, fiscal_year: int | None = None) -> list[Path]:
    """Download all filings of the given form type for a ticker.

    Returns the list of downloaded file paths.
    """
    dl = get_downloader()
    # sec_edgar_downloader returns the number of filings downloaded.
    count = dl.get(form_type, ticker, after=f"{fiscal_year}-01-01" if fiscal_year else None)
    # Locate the downloaded files in DATA_DIR/FormType/ticker/.
    ticker_dir = config.DATA_DIR / form_type / ticker
    if not ticker_dir.exists():
        return []
    return sorted(ticker_dir.rglob("*"))
