from services.embedding_service import generate_embeddings
from services.vector_store import get_collection


def search_repository(question, repo_name, top_k=3):
    """
    Search only the selected repository
    for chunks relevant to the user's question.
    """

    collection = get_collection(repo_name)

    query_embedding = generate_embeddings([question])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

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
            "distance": distances[i]
        })

    return matches