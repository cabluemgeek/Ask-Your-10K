"""Shared access to the persistent Chroma vector store used across the project."""

from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

import config


def get_vectorstore() -> Chroma:
    """Open (or create) the persistent Chroma collection used across the project."""
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(config.CHROMA_DIR),
    )