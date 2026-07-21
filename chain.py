"""Wire the retriever to an LLM: retrieve top-k chunks, build a numbered
context, and ask ChatOllama to answer strictly from that context with
citations.

This is what app.py (Streamlit) will call to turn a user's question into a
sourced answer. Keep temperature at 0 -- for finance we want reproducible,
conservative answers, not creative ones.
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

import config
from retriever import retrieve, format_citation


SYSTEM_PROMPT = """You are a financial analyst answering questions using ONLY \
the filing excerpts provided below. Do not use any outside knowledge and do \
not guess.

Rules:
- Every factual claim in your answer must be followed by a citation like [1], \
[2], referring to the numbered context blocks below.
- If multiple blocks support a claim, cite all of them, e.g. [1][3].
- If the answer is not contained in the provided context, respond exactly: \
"I don't have enough information in the retrieved filings to answer that." \
Do not fabricate an answer.
- Be concise and precise. Prefer exact figures and dates from the filings \
over paraphrased summaries.

Context:
{context}
"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "{question}"),
    ]
)


def _build_context(docs: list[Document]) -> str:
    """Turn retrieved chunks into a numbered context block for the prompt.

    Numbering here ([1], [2], ...) must match what the LLM is told to cite,
    and the same numbering is what the UI's citation panel will key off of.
    """
    blocks = []
    for i, doc in enumerate(docs, start=1):
        citation = format_citation(doc)
        blocks.append(f"[{i}] ({citation})\n{doc.page_content}")
    return "\n\n".join(blocks)


def answer(
    question: str,
    ticker: str | None = None,
    form_type: str | None = None,
    fiscal_year: int | None = None,
    k: int | None = None,
) -> str:
    """Answer a question from the filings, citing sources by [n].

    Filters are passed straight through to retriever.retrieve -- see that
    function's docstring for how they combine.
    """
    docs = retrieve(question, ticker=ticker, form_type=form_type, fiscal_year=fiscal_year, k=k)

    if not docs:
        return "I don't have enough information in the retrieved filings to answer that."

    context = _build_context(docs)

    llm = ChatOllama(model=config.OLLAMA_MODEL, temperature=0)
    chain = PROMPT | llm

    response = chain.invoke({"context": context, "question": question})
    return response.content


def answer_with_sources(
    question: str,
    ticker: str | None = None,
    form_type: str | None = None,
    fiscal_year: int | None = None,
    k: int | None = None,
) -> dict:
    """Same as answer(), but also returns the retrieved chunks for the UI.

    app.py will want this version so it can render an st.expander per cited
    chunk (ticker / form / Item / source_path) instead of just the raw text.
    """
    docs = retrieve(question, ticker=ticker, form_type=form_type, fiscal_year=fiscal_year, k=k)

    if not docs:
        return {
            "answer": "I don't have enough information in the retrieved filings to answer that.",
            "sources": [],
        }

    context = _build_context(docs)

    llm = ChatOllama(model=config.OLLAMA_MODEL, temperature=0)
    chain = PROMPT | llm

    response = chain.invoke({"context": context, "question": question})

    return {
        "answer": response.content,
        "sources": [
            {"citation": format_citation(doc), "metadata": doc.metadata, "content": doc.page_content}
            for doc in docs
        ],
    }