"""
embedding_service.py — Lazy-loaded sentence-transformer embeddings.

The model is NOT loaded at import time. It is loaded on the first call to
generate_embeddings(). This allows the FastAPI server (and /health) to start
successfully on memory-constrained environments (Render Free, 512 MB RAM)
even when the full model cannot be loaded.

If the model fails to load (OOM, missing torch, etc.) every call returns
an empty list and logs the error — the server stays up and all non-embedding
features continue to work.
"""

import logging

_log = logging.getLogger("intellionboard.embedding")

# Populated on first successful call to generate_embeddings()
_model = None
_model_error: str | None = None   # set once if load fails; avoids retry spam


def _load_model():
    """Attempt to load the sentence-transformer model (once)."""
    global _model, _model_error

    if _model is not None:
        return True
    if _model_error is not None:
        return False

    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        _log.info("Loading embedding model all-MiniLM-L6-v2 …")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        _log.info("Embedding model loaded successfully.")
        return True
    except Exception as exc:
        _model_error = str(exc)
        _log.warning(
            "Embedding model could not be loaded — AI search features will be "
            "unavailable. Error: %s", _model_error
        )
        return False


def is_available() -> bool:
    """Return True if the embedding model is loaded and ready."""
    return _load_model()


def generate_embeddings(texts: list) -> list:
    """
    Convert a list of text strings into embedding vectors.

    Returns a list of float vectors on success, or an empty list when the
    model is unavailable (so callers must check for an empty result).
    """
    if not _load_model():
        return []

    try:
        embeddings = _model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
    except Exception as exc:
        _log.error("generate_embeddings failed: %s", exc)
        return []
