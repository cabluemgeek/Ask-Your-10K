"""Parse SEC filings (HTML / iXBRL) into clean, section-aware text.

The output preserves Item / Part headings as section markers because they become
the citation anchors in the UI ("Item 1A. Risk Factors", "Item 7. MD&A", etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup


# Matches lines like:
#   Item 1.   Business
#   Item 1A.  Risk Factors
#   Item 7.   Management’s Discussion and Analysis
#   PART I
#   PART II
# Tolerates the variable whitespace 10-Ks use after the period.
_HEADING_RE = re.compile(
    r"^(?P<head>PART\s+[IVX]+|Item\s+\d+[A-Z]?\.)\s*(?P<title>.*)$",
    re.IGNORECASE,
)

# Strip patterns that show up everywhere in 10-Ks and add no signal:
#   page numbers, "/s/ Tim Cook", pure whitespace lines, etc.
_SIGNATURE_RE = re.compile(r"/s/\s+[A-Za-z .'-]+", re.IGNORECASE)
_PAGE_RE = re.compile(r"^\s*\d+\s*$")


@dataclass
class Section:
    """A logical section of a 10-K: heading + the prose that follows it."""
    heading: str          # e.g. "Item 1A. Risk Factors"  (always normalized)
    text: str             # the prose under that heading


def _normalize_heading(raw_head: str, raw_title: str) -> str:
    """Build a clean heading like "Item 1A. Risk Factors"."""
    head = raw_head.strip().upper().replace("  ", " ")
    # Normalize "Item 1a." -> "Item 1A."  (only the letter after the digit is uppercased)
    m = re.match(r"^ITEM\s+(\d+)([A-Z]?)\.?$", head, re.IGNORECASE)
    if m:
        num, letter = m.group(1), m.group(2).upper()
        head = f"Item {num}{letter}." if letter else f"Item {num}."
    elif head.startswith("PART"):
        head = head.title()  # "PART I" -> "Part I"
    title = raw_title.strip()
    return f"{head} {title}".strip() if title else head


def parse_html_filing(path: Path) -> list[Section]:
    """Parse a SEC .htm filing into a list of Sections, in document order.

    Items with no detected heading fall into a single default section so no text
    is silently dropped.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "lxml")

    # Drop noise elements: scripts, styles, hidden blocks, table-of-contents anchors.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    sections: list[Section] = []
    current = Section(heading="Cover Page", text="")
    sections.append(current)

    # Walk every text-bearing element so headings interleaved with paragraphs are captured.
    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "div", "span", "td"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        # Skip pure page numbers.
        if _PAGE_RE.match(text):
            continue
        # Skip signature lines ("/s/ Tim Cook").
        if _SIGNATURE_RE.search(text):
            continue

        m = _HEADING_RE.match(text)
        if m:
            current = Section(heading=_normalize_heading(m.group("head"), m.group("title")), text="")
            sections.append(current)
        else:
            # Collapse internal whitespace before appending.
            current.text += re.sub(r"\s+", " ", text) + " "

    # Drop empty sections and trim trailing whitespace.
    return [Section(heading=s.heading, text=s.text.strip()) for s in sections if s.text.strip()]


def parse_filing(path: Path) -> list[Section]:
    """Dispatch on file extension. Only HTML is supported for now; 10-Ks ship as .htm."""
    suffix = path.suffix.lower()
    if suffix in {".htm", ".html"}:
        return parse_html_filing(path)
    raise ValueError(f"Unsupported filing format: {path.suffix}  (only .htm / .html are supported)")
