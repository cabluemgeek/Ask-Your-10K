"""CLI: download a filing, parse it, chunk it, embed it, and store it in Chroma.

Usage:
    python ingest.py --ticker AAPL --form 10-K --year 2024

Pipeline: download -> parse -> derive fiscal year from document -> merge
sections -> chunk -> embed -> upsert into Chroma. Each chunk's metadata
carries {ticker, form_type, fiscal_year, item, source_path} so the
retriever/UI can show citations later.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

import config
from store import get_vectorstore
from sources.sec_client import download_filing
from sources.parsers import parse_filing, merge_sections


# Matches SEC 10-K cover-page language, on the already-parsed (tag-stripped) text:
#   "For the fiscal year ended September 27, 2025"
# Tolerant of non-breaking spaces (\xa0) and stray spaces before the comma,
# both of which show up in real SEC filings and break naive whitespace matching.
_FY_FROM_COVER_RE = re.compile(
    r"for the fiscal year ended\s+[A-Za-z]+\s+\d{1,2}\s*,\s*(\d{4})",
    re.IGNORECASE,
)


def find_primary_html(files: list[Path]) -> Path | None:
    """Pick the primary HTML document out of everything download_filing returned.

    sec_edgar_downloader saves full-submission.txt (raw SGML, not usable) alongside
    primary-document.html (the real filing) in each accession folder. We only want
    the .html ones.
    """
    html_files = [f for f in files if f.suffix.lower() in (".html", ".htm") and f.is_file()]
    if not html_files:
        return None
    return sorted(html_files)[-1]


def detect_fiscal_year(html_path: Path) -> int | None:
    """Find the filing's real fiscal year from its parsed Cover Page section.

    Searches the already-parsed, tag-stripped text (via parse_filing) rather than
    raw HTML, since SEC's iXBRL tagging often splits the cover-page date across
    nested tags that a raw-HTML regex won't match. Whitespace is normalized first
    because SEC filings frequently use non-breaking spaces (\\xa0) here.
    """
    try:
        sections = parse_filing(html_path)
    except Exception:
        return None

    cover = next((s for s in sections if s.heading == "Cover Page"), None)
    if cover is None:
        return None

    normalized = cover.text.replace("\xa0", " ")
    m = _FY_FROM_COVER_RE.search(normalized)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def chunk_sections(
    sections: list,
    ticker: str,
    form_type: str,
    fiscal_year: int | None,
    source_path: Path,
) -> list[Document]:
    """Turn merged Sections into LangChain Documents, chunked with metadata.

    Each chunk keeps track of which Item it came from -- this is what lets the UI
    render a real citation ("AAPL 10-K, Item 1A. Risk Factors") instead of just
    dumping raw text at the user.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    documents: list[Document] = []
    for section in sections:
        chunks = splitter.split_text(section.text)
        for i, chunk in enumerate(chunks):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "ticker": ticker,
                        "form_type": form_type,
                        "fiscal_year": fiscal_year or 0,
                        "item": section.heading,
                        "source_path": str(source_path),
                        "chunk_index": i,
                    },
                )
            )
    return documents



def ingest(ticker: str, form_type: str, year: int | None) -> None:
    print(f"[1/4] Downloading {form_type} for {ticker} (after {year})...")
    files = download_filing(ticker, form_type, year)
    print(f"      -> {len(files)} files/dirs found")

    html_path = find_primary_html(files)
    if html_path is None:
        print("      !! No primary HTML document found. Nothing to parse.")
        return
    print(f"      -> using {html_path}")

    # Pull the *real* fiscal year from the document so the citation is correct
    # even when --year was used as a "after" filter. Falls back to the CLI value
    # (which is just the year the user wants to start looking from).
    doc_fy = detect_fiscal_year(html_path)
    if doc_fy is not None:
        fiscal_year = doc_fy
        print(f"      -> fiscal year detected from cover page: {fiscal_year}")
    else:
        fiscal_year = year
        print(f"      -> could not detect fiscal year from cover; using CLI value: {year}")

    print("[2/4] Parsing...")
    raw_sections = parse_filing(html_path)
    sections = merge_sections(raw_sections)
    print(f"      -> {len(raw_sections)} raw sections -> {len(sections)} merged")

    print("[3/4] Chunking...")
    documents = chunk_sections(sections, ticker, form_type, fiscal_year, html_path)
    print(f"      -> {len(documents)} chunks (chunk_size={config.CHUNK_SIZE}, overlap={config.CHUNK_OVERLAP})")

    print("[4/4] Embedding + storing in Chroma (this may take a minute on first run)...")
    vectorstore = get_vectorstore()
    ids = [
        f"{ticker}-{form_type}-{fiscal_year}-{d.metadata['item']}-{d.metadata['chunk_index']}"
        for d in documents
    ]
    vectorstore.add_documents(documents, ids=ids)
    print(f"      -> stored {len(documents)} chunks in collection '{config.COLLECTION_NAME}'")
    print(f"      -> persisted to {config.CHROMA_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download, parse, chunk, embed, and store a SEC filing.")
    parser.add_argument("--ticker", required=True, help="e.g. AAPL")
    parser.add_argument("--form", required=True, help="e.g. 10-K")
    parser.add_argument("--year", type=int, default=None, help="only filings after this year")
    args = parser.parse_args()
    ingest(args.ticker, args.form, args.year)


if __name__ == "__main__":
    main()