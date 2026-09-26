"""
retriever.py — Vector similarity search with graceful degradation.

If the embedding model or ChromaDB are unavailable (e.g. on Render Free
where 512 MB RAM cannot hold the model) this module returns an empty list
rather than raising. All endpoints that call search_repository() already
handle an empty results list correctly.
"""

import logging

from services.embedding_service import generate_embeddings
from services.vector_store import get_collection

_log = logging.getLogger("intellionboard.retriever")


def search_repository(question: str, repo_name: str, top_k: int = 3) -> list:
    """
    Search the repository's vector index for chunks relevant to *question*.

    Returns a list of match dicts, or an empty list when the embedding model
    or ChromaDB are unavailable.
    """
    # Generate query embedding — returns [] when model is not loaded
    query_embeddings = generate_embeddings([question])
    if not query_embeddings:
        _log.debug(
            "search_repository: embedding unavailable — returning empty results "
            "for repo=%s question=%.60s", repo_name, question
        )
        return []

    collection = get_collection(repo_name)
    if collection is None:
        _log.debug("search_repository: ChromaDB collection unavailable for %s", repo_name)
        return []

    try:
        results = collection.query(
            query_embeddings=[query_embeddings[0]],
            n_results=top_k,
        )
    except Exception as exc:
        _log.warning("ChromaDB query failed for %s: %s", repo_name, exc)
        return []

    matches = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i in range(len(documents)):
        matches.append({
            "repository": metadatas[i]["repository"],
            "file": metadatas[i]["file"],
            "chunk_id": metadatas[i]["chunk_id"],
            "content": documents[i],
            "distance": distances[i],
        })

    return matches
