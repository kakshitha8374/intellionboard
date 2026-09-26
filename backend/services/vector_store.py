"""
vector_store.py — ChromaDB persistence with lazy initialisation.

The chromadb.PersistentClient is created on first use, not at import time.
This prevents the import chain  main → vector_store → embedding_service
from triggering PyTorch/SentenceTransformer loading during server startup.

Every public function is guarded: if ChromaDB or embeddings are unavailable
it returns a safe error dict/empty list rather than raising, so the FastAPI
server and all non-embedding endpoints keep working.
"""

import logging
import os

from services.embedding_service import generate_embeddings, is_available as embeddings_available

_log = logging.getLogger("intellionboard.vector_store")

_client = None
_client_error: str | None = None


def _get_client():
    """Return (or lazily create) the ChromaDB persistent client."""
    global _client, _client_error

    if _client is not None:
        return _client
    if _client_error is not None:
        return None

    try:
        import chromadb  # noqa: PLC0415
        db_path = os.environ.get("CHROMA_DB_PATH", "chroma_db")
        _client = chromadb.PersistentClient(path=db_path)
        _log.info("ChromaDB client initialised at %s", db_path)
        return _client
    except Exception as exc:
        _client_error = str(exc)
        _log.warning("ChromaDB unavailable — vector search disabled. Error: %s", _client_error)
        return None


def get_collection(repo_name: str):
    """
    Return a ChromaDB collection for the given repository.
    Returns None if ChromaDB is unavailable.
    """
    client = _get_client()
    if client is None:
        return None

    collection_name = f"repo_{repo_name.lower().replace('-', '_')}"
    try:
        return client.get_or_create_collection(name=collection_name)
    except Exception as exc:
        _log.error("get_collection(%s) failed: %s", repo_name, exc)
        return None


def store_chunks(chunks: list, repo_name: str) -> dict:
    """
    Embed and store repository chunks in ChromaDB.

    Returns a status dict. If embeddings or ChromaDB are unavailable the
    function returns an error dict rather than raising — the analysis job
    still completes with core metrics intact.
    """
    if not chunks:
        return {"status": "error", "message": "No chunks to store"}

    if not embeddings_available():
        return {
            "status": "unavailable",
            "message": "Embedding model not loaded — vector index skipped.",
        }

    collection = get_collection(repo_name)
    if collection is None:
        return {
            "status": "unavailable",
            "message": "ChromaDB unavailable — vector index skipped.",
        }

    texts = [chunk["content"] for chunk in chunks]
    embeddings = generate_embeddings(texts)

    if not embeddings:
        return {
            "status": "error",
            "message": "Embedding generation returned empty result.",
        }

    ids = [
        f"{repo_name}_{chunk['file']}_{chunk['chunk_id']}"
        for chunk in chunks
    ]
    metadatas = [
        {
            "repository": repo_name,
            "file": chunk["file"],
            "chunk_id": chunk["chunk_id"],
        }
        for chunk in chunks
    ]

    try:
        collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
    except Exception as exc:
        _log.error("ChromaDB upsert failed: %s", exc)
        return {"status": "error", "message": str(exc)}

    return {
        "status": "success",
        "repository": repo_name,
        "stored_chunks": len(chunks),
    }
