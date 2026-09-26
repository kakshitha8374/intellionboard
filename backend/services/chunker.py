"""
chunker.py — Text chunking with per-file content truncation.

Limits chunk count per file to avoid flooding the vector store with
one huge file's content. Prioritizes beginning of each file (most
important context is usually at the top).
"""


# Limits to avoid vector store explosion
MAX_CONTENT_CHARS_PER_FILE = 8000   # Truncate file content before chunking
MAX_CHUNKS_PER_FILE = 8             # Cap chunks per file


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Divide text into smaller overlapping chunks.
    """
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Convert extracted documents into smaller chunks.

    Truncates each file's content before chunking to prevent a single
    large file from dominating the vector store.
    """
    all_chunks = []

    for document in documents:
        file_name = document["file"]
        content = document["content"]

        # Truncate to prevent huge files from generating thousands of chunks
        if len(content) > MAX_CONTENT_CHARS_PER_FILE:
            content = content[:MAX_CONTENT_CHARS_PER_FILE]

        chunks = chunk_text(content)

        # Cap chunks per file
        chunks = chunks[:MAX_CHUNKS_PER_FILE]

        for index, chunk in enumerate(chunks):
            all_chunks.append({
                "file": file_name,
                "chunk_id": index,
                "content": chunk,
            })

    return all_chunks
