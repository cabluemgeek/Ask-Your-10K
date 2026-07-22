# Ask Your 10-K

A local, citation-grounded RAG (Retrieval-Augmented Generation) assistant for SEC 10-K filings. Ask a question in plain English about a company's financials, risks, or disclosures, and get an answer sourced to the exact filing and section it came from — not a hallucinated summary.

Built as a finance × GenAI portfolio project: it demonstrates the full RAG stack (embeddings, vector search, retrieval, prompt engineering, grounded generation) applied to real financial documents where **verifiability matters more than fluency**.

## Why this exists

Generic chatbots will confidently answer financial questions with numbers they made up. This project takes the opposite approach: every factual claim in an answer must be tied to a citation `[n]` that maps to a real, retrieved excerpt from an actual SEC filing. If the answer isn't in the filings that were ingested, the assistant says so instead of guessing.

## What it does

- Downloads real 10-K filings directly from SEC EDGAR for any ticker
- Parses the filing's structure (Item 1. Business, Item 1A. Risk Factors, Item 7. MD&A, etc.) so citations point to a specific section, not just "somewhere in a 900-page document"
- Chunks and embeds the text locally (Hugging Face sentence-transformers — no API key required)
- Stores everything in a persistent local vector database (ChromaDB)
- Answers questions using a local LLM (Ollama, `llama3.2`) — no data leaves your machine, no API costs
- Lets you filter by ticker, form type, and fiscal year, and ingest multiple years of history for the same company
- Shows the exact source excerpt behind every citation in the UI, so you can verify the answer yourself

## Tech stack

| Layer | Tool |
|---|---|
| UI | Streamlit |
| LLM | Ollama (`llama3.2`), via LangChain |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2`, local (Hugging Face) |
| Vector store | ChromaDB (persistent, local) |
| Filing source | SEC EDGAR (`sec-edgar-downloader`) |
| Parsing | BeautifulSoup + lxml, custom section-detection logic |
| Orchestration | LangChain (retriever, prompt templates, chunking) |

## Screenshot

*(add a screenshot of the chat UI here once you have one — e.g. `![screenshot](docs/screenshot.png)`)*

## How to run it locally

```bash
# 1. Clone and set up the environment
git clone <your-repo-url>
cd ask-your-10-k
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; use venv/bin/activate on macOS/Linux
pip install -r requirements.txt

# 2. Set up Ollama (local LLM, free)
ollama pull llama3.2

# 3. Configure your .env
# Copy .env.example to .env and set SEC_USER_AGENT to your own name + email
# (SEC EDGAR requires this — see https://www.sec.gov/os/webmaster-faq#developers)

# 4. Ingest a filing (first run downloads + embeds, takes a few minutes)
python ingest.py --ticker AAPL --form 10-K --year 2015

# 5. Launch the app
streamlit run app.py
```

Then open the local URL Streamlit prints, pick a ticker/year in the sidebar, and start asking questions.

## Evaluation

A small hand-written eval set (`eval/`) checks the pipeline systematically rather than anecdotally — verifying that answers are properly cited, that fiscal-year filtering actually returns chunks from the right year, and that out-of-scope questions (weather, other companies, live stock prices) are correctly refused rather than fabricated.

```bash
python -m eval.run_eval
```

This writes a scored report to `eval/results.md`.

## Limitations (read before trusting an answer)

- **Model size:** running on `llama3.2` locally (not GPT-4-class) for cost/privacy reasons. It occasionally omits a citation marker even when instructed to include one — always check the "Sources" panel yourself rather than trusting the prose alone.
- **Numerical reasoning:** local models are weaker than frontier models at multi-step arithmetic (e.g., computing a ratio across two cited figures). Treat computed/derived numbers with extra scrutiny; verbatim figures from the filing are more reliable.
- **Coverage:** only 10-K filings for the years you've explicitly ingested are searchable. A question about a year you haven't ingested will (correctly) be refused, not guessed.
- **Cross-company comparison:** the retriever filters by ticker, so comparing two companies in one question isn't currently supported — ask about each separately.
- **Not investment advice:** this is a document Q&A tool, not a financial advisor. Always verify figures against the primary source (the citation panel links to the exact filing).

## Project structure

```
.
├── app.py              # Streamlit UI
├── ingest.py            # CLI: download → parse → chunk → embed → store
├── retriever.py          # Vector search with metadata filtering
├── chain.py              # Prompt + LLM call, builds cited answers
├── store.py               # Shared Chroma vector store access
├── config.py               # Central config (paths, model names, chunk size)
├── sources/
│   ├── sec_client.py        # SEC EDGAR download wrapper
│   └── parsers.py            # HTML → structured, section-aware text
├── eval/
│   ├── eval_questions.py      # Hand-written test cases
│   └── run_eval.py             # Automated scoring + report
└── requirements.txt
```
