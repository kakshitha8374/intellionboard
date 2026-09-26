from sentence_transformers import SentenceTransformer


# Free local embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")


def generate_embeddings(texts):
    """
    Convert text into numerical embeddings.
    """

    embeddings = model.encode(
        texts,
        show_progress_bar=False
    )

    return embeddings.tolist()