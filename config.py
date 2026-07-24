"""Project-wide configuration. The only file that knows paths, model
  names, and tunables."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env once, at import time. .env is gitignored.
load_dotenv()

# --- Paths ---
# Resolve relative to this file so the project works no matter where it's
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = PROJECT_ROOT / "chroma"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# --- Models ---
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL",
"sentence-transformers/all-MiniLM-L6-v2")

# --- SEC client ---
# SEC EDGAR requires a real User-Agent (name + email). Without it, requests are blocked.
SEC_USER_AGENT = os.getenv(
      "SEC_USER_AGENT",
      "AskYour10K research@example.com",  # change this to your own
  )

# --- Retrieval / chunking ---
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
RETRIEVAL_K = 6
COLLECTION_NAME = "filings"