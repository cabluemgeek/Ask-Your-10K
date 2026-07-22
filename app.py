"""Streamlit UI for Ask Your 10-K.

The backend is chain.py + retriever.py + store.py. This file only handles
the user-facing bits: sidebar filters, chat input, answer rendering, and
a per-citation expander so users can see where each claim came from.

Run with: streamlit run app.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

import config
from chain import answer_with_sources
from store import get_vectorstore


# --- Page setup --------------------------------------------------------------
# set_page_config must be the first Streamlit call.
st.set_page_config(
    page_title="Ask Your 10-K",
    page_icon="📊",  # bar chart
    layout="wide",
)


# --- Cached resources --------------------------------------------------------
# Streamlit re-runs this script on every interaction. Wrapping the vectorstore
# in @st.cache_resource means we open Chroma once per session, not per click.
@st.cache_resource
def cached_vectorstore():
    return get_vectorstore()

def get_available_years(ticker: str | None, form_type: str | None) -> list[int]:
    """List the distinct fiscal years actually present in the store for this filter."""
    vs = cached_vectorstore()
    where: dict | None = None
    conds = []
    if ticker:
        conds.append({"ticker": ticker})
    if form_type:
        conds.append({"form_type": form_type})
    if conds:
        where = conds[0] if len(conds) == 1 else {"$and": conds}
    result = vs._collection.get(where=where, include=["metadatas"])  # type: ignore[attr-defined]
    years = {m["fiscal_year"] for m in result["metadatas"] if m.get("fiscal_year")}
    return sorted(years)

def count_chunks(ticker: str | None, form_type: str | None, fiscal_year: int | None) -> int:
    """Count chunks in the store, optionally filtered by metadata."""
    vs = cached_vectorstore()
    where: dict | None = None
    if ticker or form_type or fiscal_year:
        conds = []
        if ticker:
            conds.append({"ticker": ticker})
        if form_type:
            conds.append({"form_type": form_type})
        if fiscal_year:
            conds.append({"fiscal_year": fiscal_year})
        where = conds[0] if len(conds) == 1 else {"$and": conds}
    # Chroma's Collection.count() takes no filter; use get() and count ids instead.
    result = vs._collection.get(where=where, include=[])  # type: ignore[attr-defined]
    return len(result["ids"])


def trigger_ingest(ticker: str, form_type: str, year: int | None) -> str:
    """Re-run ingest.py as a subprocess so the user sees the same logs as the CLI."""
    cmd = [sys.executable, "ingest.py", "--ticker", ticker, "--form", form_type]
    if year is not None:
        cmd += ["--year", str(year)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(config.PROJECT_ROOT))
    return (result.stdout or "") + (result.stderr or "")


# --- Sidebar -----------------------------------------------------------------
with st.sidebar:
    st.header("Ask Your 10-K")
    st.caption("Query SEC filings with grounded, cited answers.")

    ticker = st.text_input("Ticker", value="AAPL", help="e.g. AAPL, MSFT, NVDA").upper().strip()
    form_type = st.selectbox("Form type", options=["10-K", "10-Q", "8-K"], index=0)

    download_since_year = st.number_input(
        "Download filings since",
        min_value=2000,
        max_value=2030,
        value=2015,
        step=1,
        help="Used only when ingesting: fetches every filing dated after January 1 of this year.",
    )

    available_years = sorted(get_available_years(ticker or None, form_type), reverse=True)
    year_options = ["All years"] + [str(y) for y in available_years]
    selected_year_label = st.selectbox(
        "Query fiscal year",
        options=year_options,
        index=0,
        help="Restrict the chat to one fiscal year's filing, or search across all ingested years.",
    )
    query_year = None if selected_year_label == "All years" else int(selected_year_label)

    st.divider()

    # Show how many chunks are in the store for the current selection.
    try:
        n = count_chunks(ticker or None, form_type, query_year)
        st.metric("Chunks for this filter", n)
    except Exception as exc:
        st.warning(f"Could not query the store: {exc}")
        n = 0

    if st.button("Ingest / re-ingest this filing", use_container_width=True):
        with st.spinner(f"Downloading + parsing + embedding {ticker} {form_type}..."):
            log = trigger_ingest(ticker, form_type, int(download_since_year))
        st.success("Done. Scroll down to ask a question.")
        with st.expander("Ingest log"):
            st.code(log, language="text")
        st.cache_resource.clear()
        st.rerun()

    st.divider()
    st.caption(
        "Pipeline: SEC EDGAR → HTML parser → chunker → "
        "Hugging Face embeddings → Chroma → Ollama (llama3.2)."
    )


# --- Main chat area ----------------------------------------------------------
st.title("Ask Your 10-K")
st.caption(
    "Answers are grounded in the retrieved excerpts only. Every factual claim is "
    "followed by a citation like [1] that maps to a source chunk below."
)

# Empty state: if nothing is in the store, prompt the user to ingest first.
if n == 0:
    st.info(
        "No chunks found for this filter yet. Click **Ingest / re-ingest this filing** "
        "in the sidebar to download and index a 10-K. The first ingest takes 2–3 minutes."
    )
    st.stop()

# Chat history (kept in session_state so it persists across re-runs).
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if question := st.chat_input("e.g. What was total revenue in fiscal year 2025?"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving context and generating answer (30–60s on CPU)..."):
            result = answer_with_sources(
                question,
                ticker=ticker or None,
                form_type=form_type,
                fiscal_year=query_year,
            )
        st.markdown(result["answer"])

        if result["sources"]:
            st.markdown("**Sources**")
            for i, src in enumerate(result["sources"], start=1):
                with st.expander(f"[{i}] {src['citation']}"):
                    st.caption(f"source file: `{src['metadata'].get('source_path', '?')}`")
                    st.text(src["content"])

    st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
