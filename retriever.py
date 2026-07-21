"""Turn the Chroma vector store into a retriever, with optional metadata filtering.

This is what chain.py calls to get the top-k chunks for a question, and what the
UI's citation panel renders metadata from.
"""

from __future__ import annotations

from langchain_core.documents import Document

import config
from store import get_vectorstore


def retrieve(
    query: str,
    ticker: str | None = None,
    form_type: str | None = None,
    fiscal_year: int | None = None,
    k: int | None = None,
) -> list[Document]:
    """Return the top-k chunks most relevant to query, optionally filtered by metadata.

    Filters are combined with AND when more than one is given. Pass None (the
    default) for any filter you don't want to apply -- e.g. retrieve(q, ticker="AAPL")
    searches only AAPL's filings, across any form type or year.
    """
    vectorstore = get_vectorstore()
    top_k = k or config.RETRIEVAL_K

    filter_dict: dict[str, object] = {}
    if ticker:
        filter_dict["ticker"] = ticker
    if form_type:
        filter_dict["form_type"] = form_type
    if fiscal_year:
        filter_dict["fiscal_year"] = fiscal_year

    if len(filter_dict) > 1:
        # Chroma's filter syntax requires $and for multiple conditions.
        # Use `key` instead of `k` here so we don't shadow the top_k count above.
        where = {"$and": [{key: val} for key, val in filter_dict.items()]}
    elif filter_dict:
        where = filter_dict
    else:
        where = None

    return vectorstore.similarity_search(query, k=top_k, filter=where)


def format_citation(doc: Document) -> str:
    """Build a short, human-readable citation string from a chunk's metadata."""
    m = doc.metadata
    return f"{m['ticker']} {m['form_type']} ({m['fiscal_year']}) \u2014 {m['item']}"