import chromadb
from services.embedding_service import generate_embeddings


# Local ChromaDB database
client = chromadb.PersistentClient(path="chroma_db")


def get_collection(repo_name):
    """
    Get a separate ChromaDB collection for each repository.
    """

    collection_name = f"repo_{repo_name.lower().replace('-', '_')}"

    return client.get_or_create_collection(
        name=collection_name
    )


def store_chunks(chunks, repo_name):
    """
    Store repository chunks and embeddings
    in a repository-specific ChromaDB collection.
    """

    if not chunks:
        return {
            "status": "error",
            "message": "No chunks to store"
        }

    collection = get_collection(repo_name)

    texts = [
        chunk["content"]
        for chunk in chunks
    ]

    embeddings = generate_embeddings(texts)

    ids = [
        f"{repo_name}_{chunk['file']}_{chunk['chunk_id']}"
        for chunk in chunks
    ]

    metadatas = [
        {
            "repository": repo_name,
            "file": chunk["file"],
            "chunk_id": chunk["chunk_id"]
        }
        for chunk in chunks
    ]

    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return {
        "status": "success",
        "repository": repo_name,
        "stored_chunks": len(chunks)
    }