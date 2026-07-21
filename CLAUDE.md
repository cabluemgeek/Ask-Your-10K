# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: Ask Your 10-K — Financial RAG Assistant

A retrieval-augmented generation system that lets users query SEC filings (10-K/10-Q), earnings call transcripts, or analyst reports in natural language and receive grounded, cited answers instead of hallucinated summaries.

Portfolio context: this project targets asset-management / fintech roles. Every architectural choice should optimise for "demonstrable, defensible, finance-aware" rather than "clever ML."

## Environment (already set up)

- **Python**: 3.12.10, virtualenv at `./venv/`
- **OS**: Windows 11 (Git Bash). Use forward slashes in paths; Python itself is invoked as `python` (not `python3` on this box).
- **LLM backend**: Ollama (local, free). Installed at v0.32.1; **no model pulled yet** — this is the first blocker to resolve.
- **Embeddings**: local Hugging Face `sentence-transformers` (no API key required).
- **Vector store**: ChromaDB (already installed at v1.5.9).
- **Frameworks already installed** in `venv/`: `streamlit`, `langchain` v1.3, `langchain-openai`, `langchain-community`, `langchain-text-splitters`, `sentence-transformers`, `transformers`, `sec_edgar_downloader`, `pypdfium2`, `pydantic`, `python-dotenv`, `requests`.
- **`.env`**: exists, contains only an empty `OPEN_AI_KEY=`. The key is intentionally left blank because the project uses Ollama — do not try to populate it.

## Commands

> Always activate the venv first: `source venv/Scripts/activate` (Git Bash) or `venv\Scripts\activate` (cmd/PowerShell). The venv is at `./venv`.

| Action | Command |
| --- | --- |
| Activate venv (Git Bash) | `source venv/Scripts/activate` |
| Install a new dependency | `pip install PACKAGE_NAME` then `pip freeze > requirements.txt` (e.g. `pip install langchain-ollama`) |
| Pull the local LLM (one-time) | `ollama pull llama3.2` (or `mistral`, `phi3`, `gemma2:2b` for lighter machines) |
| Verify Ollama is reachable | `curl http://localhost:11434/api/version` |
| List pulled models | `ollama list` |
| Run the Streamlit app | `streamlit run app.py` |
| Ingest a filing into the vector store | `python ingest.py --ticker AAPL --form 10-K --year 2024` |
| Run a single retrieval smoke test | `python -m pytest tests/test_retrieval.py -q` |
| Lint | `ruff check .` (add `ruff` to the venv if absent) |

> **Never type `pip install <pkg>` literally.** Both bash and PowerShell treat `<` as a redirection operator and will refuse to parse the command. Always substitute the real package name (e.g. `pip install langchain-ollama`).

## High-level architecture

The system is a standard RAG pipeline with one finance-specific twist: every retrieved chunk must carry a citation (filing type, company, fiscal year, page/section) so the UI can show users *where* an answer came from. Citations are the differentiator — in finance, an uncited answer is worse than no answer.

```
                ┌────────────────────┐
                │  SEC EDGAR / PDFs  │  sec_edgar_downloader
                └─────────┬──────────┘
                          │ raw .htm / .pdf
                          ▼
                ┌────────────────────┐
                │  ingest.py         │  one-time / on-demand
                │  - parse (BS4/htm) │
                │  - chunk (LC)      │
                │  - embed (HF ST)   │
                │  - upsert (Chroma) │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │  ChromaDB store    │  persistent, ./chroma/
                └─────────┬──────────┘
                          │ top-k chunks + metadata
                          ▼
   user query ──► retriever.py ──► prompt builder ──► Ollama (llama3.2)
                                                       │
                                                       ▼
                                              answer + citations
                                                       │
                                                       ▼
                                                 app.py (Streamlit)
```

### Module layout (target)

```
.
├── app.py                    # Streamlit UI — entrypoint for the demo
├── ingest.py                 # CLI: download → parse → chunk → embed → store
├── retriever.py              # query → top-k chunks (with metadata) from Chroma
├── chain.py                  # prompt template + Ollama call; assembles answer+citations
├── config.py                 # loads .env, exposes constants (model names, paths, k)
├── sources/
│   ├── sec_client.py         # wrapper around sec_edgar_downloader
│   └── parsers.py            # HTML / PDF → clean text, preserves section headings
├── tests/
│   ├── test_parsers.py
│   ├── test_retrieval.py
│   └── test_chain.py
├── data/                     # raw filings, gitignored
├── chroma/                   # vector store, gitignored
└── requirements.txt
```

`config.py` is the single source of truth for paths, model names, chunk size, and `k` (retrieval depth). Every other module imports from it — no hard-coded model names or paths elsewhere.

### Data flow & responsibilities

1. **`sources/sec_client.py`** — given a ticker + form type + year, downloads from EDGAR via `sec_edgar_downloader`. Set a descriptive `User-Agent` (SEC requires it; use `Name email`). Caches under `data/`.
2. **`sources/parsers.py`** — converts the raw filing to clean text. 10-Ks are HTML with heavy boilerplate (cover-page signatures, exhibits). Strip the boilerplate but **preserve Item / Part headings** (`Item 1. Business`, `Item 7. MD&A`, `Item 8. Financial Statements`) — these become citation anchors. Use `BeautifulSoup` for HTML and `pypdfium2` for any PDF rendering.
3. **`ingest.py`** — chunks with `langchain_text_splitters.RecursiveCharacterTextSplitter` (start at ~1000 chars, 150 overlap — 10-K prose is dense, larger chunks retain context). Embeds with `sentence-transformers/all-MiniLM-L6-v2` (fast, 384-dim, good enough for finance prose; switch to `all-mpnet-base-v2` if quality is lacking). Each chunk's metadata: `{ticker, form, fiscal_year, item, source_url, page_hint}`. Upserts to Chroma with `collection_name="filings"`.
4. **`retriever.py`** — `Chroma.as_retriever(search_kwargs={"k": 5})` filtered by metadata when the UI specifies a ticker/year. Returns `Document` objects whose `.metadata` is what the UI renders as the citation chip.
5. **`chain.py`** — builds a prompt with: (a) the question, (b) numbered context chunks, (c) an instruction to cite by `[n]` referencing the numbered chunks, (d) a refusal fallback ("if the answer is not in the context, say so"). Calls Ollama via `langchain_ollama.ChatOllama` (add this package — see step 4 below). Returns `(answer_text, [citation_dict])`.
6. **`app.py`** — Streamlit with three panels: sidebar (ticker/year selector, button to ingest), main (chat input + answer), expander (the retrieved chunks shown as expandable citations). Citations must be clickable/visible — that is the whole point of the project for a finance audience.

## Roadmap (end-to-end)

Work through these in order. Do not skip ahead — each step depends on the previous.

### Step 0 — Verify the environment (now)
- [ ] `ollama serve` is running (start it; on Windows it may already be a background service — check Task Manager).
- [ ] `curl http://localhost:11434/api/version` returns a version string.
- [ ] `ollama pull llama3.2` — first pull is ~2 GB. Use `llama3.2:1b` or `phi3:mini` if the machine is slow.
- [ ] `ollama list` shows the model.
- [ ] Quick sanity check: `ollama run llama3.2 "say hi"` in a terminal.

### Step 1 — Lock the configuration
- [ ] Create `config.py` reading `.env` via `python-dotenv`. Constants: `OLLAMA_MODEL`, `EMBEDDING_MODEL`, `CHROMA_DIR`, `DATA_DIR`, `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=150`, `RETRIEVAL_K=5`, `COLLECTION_NAME="filings"`.
- [ ] Pin everything in `requirements.txt`: `pip freeze > requirements.txt`.
- [ ] Add a `.gitignore`: `data/`, `chroma/`, `__pycache__/`, `.env`.

### Step 2 — Build the SEC client + parser
- [ ] `sources/__init__.py`, `sources/sec_client.py` — wrapper around `sec_edgar_downloader`. Required: a real `User-Agent` string (e.g. `"AskYour10K research@example.com"`). SEC blocks default user agents.
- [ ] `sources/parsers.py` — extract text from `.htm` filings, strip nav/cover boilerplate, **keep Item headings** as section markers. Use `BeautifulSoup` with `lxml` parser.
- [ ] Smoke test: download Apple's most recent 10-K and confirm the parsed text contains "Item 1." and "Item 7." headings.

### Step 3 — Build the ingestion pipeline
- [ ] `ingest.py` — argparse CLI: `--ticker`, `--form`, `--year`. Orchestrates: download → parse → chunk → embed → upsert.
- [ ] Use `RecursiveCharacterTextSplitter` with separators tuned for prose (`["\n\n", "\n", ". ", " ", ""]`).
- [ ] Embed with `HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")` from `langchain_community.embeddings`.
- [ ] Persist Chroma to `./chroma/`. Verify with `chroma.list_collections()`.
- [ ] First real ingest: 2–3 companies (e.g. AAPL, MSFT, NVDA), 10-K only, latest year. Enough for a demo; do not ingest the whole EDGAR corpus.

### Step 4 — Wire the LLM
- [ ] `pip install langchain-ollama` (not in the venv yet — verify with `pip show langchain-ollama`).
- [ ] `chain.py` — `ChatOllama(model=config.OLLAMA_MODEL, temperature=0)` (temperature 0 is critical for finance — you want reproducible, conservative answers, not creative ones).
- [ ] Prompt template must include: (1) role: "you are a financial analyst answering from filings only", (2) numbered context blocks, (3) instruction to cite with `[1]`, `[2]`, etc., (4) explicit refusal clause for out-of-context questions.
- [ ] Test outside Streamlit: `python -c "from chain import answer; print(answer('What was Apple\'s revenue in FY2023?'))"`.

### Step 5 — Build the Streamlit UI
- [ ] `app.py` with `streamlit run app.py`.
- [ ] Sidebar: ticker dropdown, year dropdown, "Ingest this filing" button (calls `ingest.py` via `subprocess` so the vector store updates in the running session — or use `st.cache_resource` and re-instantiate the retriever).
- [ ] Main: `st.chat_input` for the question; render answer with markdown; under it, an `st.expander` per cited chunk showing ticker / form / Item / source URL.
- [ ] Add a "Show retrieved sources" toggle so the reviewer can see what the model saw.
- [ ] Empty state: if no filings are ingested yet, show a friendly "Start by ingesting a 10-K in the sidebar" message.

### Step 6 — Tests
- [ ] `tests/test_parsers.py` — known 10-K excerpt → expected cleaned output. Item headings preserved.
- [ ] `tests/test_retrieval.py` — query "supply chain risk" against an ingested AAPL 10-K → top-1 chunk is from Item 1A (Risk Factors).
- [ ] `tests/test_chain.py` — answer to "What was the CEO's name?" includes a citation; answer to "What is the weather today?" refuses and does not fabricate.
- [ ] Run `pytest -q` before every commit.

### Step 7 — Portfolio polish (after MVP works)
- [ ] **Earnings-call sentiment layer**: ingest transcripts from `sec_edgar_downloader` (form 8-K, exhibit 99.1). Run a tone classifier (`ProsusAI/finbert` via `transformers.pipeline("sentiment-analysis")`) per quarter, plot tone shifts in Streamlit (`st.line_chart`). This is the "bonus" feature from the brief — and it is the one that makes a fintech recruiter stop scrolling.
- [ ] **Compare-across-companies query**: extend `retriever.py` to accept multi-ticker filters so a user can ask "How did AAPL and MSFT describe supply-chain risk differently in their 2023 10-Ks?"
- [ ] **Eval harness**: a `eval/` folder with ~20 hand-written Q&A pairs and expected citations. Run after every prompt/retrieval change. This is how you prove the system works to a hiring manager.
- [ ] **README.md**: 5-line elevator pitch, screenshot of the UI, how to run locally, what data it uses, and an honest "limitations" section (Ollama models are weaker than GPT-4 on numerical reasoning; cross-company comparison is approximate). A portfolio README that admits limits reads as more credible than one that doesn't.

## Finance-specific guardrails (read these before changing prompts)

1. **Never let the model invent numbers.** The prompt must say "answer only from the provided context; if a figure is not in the context, say 'not disclosed in the provided excerpts'." Test this — it is the most common failure mode.
2. **Citations are non-negotiable.** Every numeric or factual claim in the answer must be tied to a `[n]` that maps to a retrieved chunk whose metadata renders in the UI. `k=5` is a starting point; raise it to 8 if the model can't find an answer.
3. **Chunk boundaries should respect section boundaries.** Use `RecursiveCharacterTextSplitter` with Item-level separators when possible, so a chunk does not straddle Item 1A and Item 1B and produce nonsense citations.
4. **Fiscal year ≠ calendar year.** AAPL's FY2023 ended September 2023. Always pass `--year` and store it as `fiscal_year` metadata, not as the document date.
5. **Do not summarise across years without flagging it.** A "compare 2022 vs 2023 revenue" answer must clearly label which number is from which fiscal year.

## Things explicitly out of scope (for now)

- Fine-tuning any model. RAG is the project; fine-tuning dilutes the story.
- A real-time price feed or trading signal. This is a research tool, not a trading bot.
- Multi-document agent loops (LangGraph, ReAct). The straight retrieve-then-generate chain is enough for the demo and easier to defend in an interview.
- Production deployment (Docker, cloud, auth). The portfolio goal is a local demo you can show in 5 minutes.

## First concrete action (what to do right now)

```bash
cd ~/Desktop/Projets\ -\ github/Ask\ Your\ 10-K
source venv/Scripts/activate
which python   # MUST end in .../Ask Your 10-K/venv/Scripts/python — if not, see "Windows venv gotchas" below
ollama serve &          # if not already running
ollama pull llama3.2    # one-time, ~2 GB
ollama list             # confirm
```

Once `ollama list` shows `llama3.2` and `which python` returns a path inside the project's `venv/`, move to Step 1 and create `config.py`. Then run `pip freeze > requirements.txt` so the project is reproducible.

### Windows venv gotchas (Git Bash on Windows 11)

These bit me on first setup — they will bite future Claude sessions too:

- **Shell display vs. actual activation.** A prompt showing `(venv)` is **not proof** the venv is active. Always run `which python` and confirm the path is inside `.../Ask Your 10-K/venv/`. If `which python` returns the system path, packages install into the system Python and silently pollute it.
- **Double-paren prompt `((venv) )`.** Cosmetic. The venv still works. To reset: `deactivate` then `source venv/Scripts/activate` again.
- **Path with spaces.** The project lives in `.../Projets - github/Ask Your 10-K/`. In Git Bash, escape it: `cd ~/Desktop/Projets\ -\ github/Ask\ Your\ 10-K`. Or open VS Code directly in that folder (`File → Open Folder`) and use its integrated terminal — paths then work without escaping.
- **The misleading `.venv` directory.** If a previous attempt created a hidden `.venv/`, ignore it. The real venv is `venv/` (no leading dot). Recreate cleanly with `rm -rf venv && python -m venv venv` if state is uncertain.
- **PowerShell users.** `<pkg>` is a reserved token in PowerShell. Always use Git Bash for this project, or quote package names: `pip install "langchain-ollama"`.
- **VS Code interpreter.** `Ctrl+Shift+P` → `Python: Select Interpreter` → pick `...\Ask Your 10-K\venv\Scripts\python.exe`. After this, every new VS Code terminal auto-activates and `which python` returns the venv path without any `source` command.
