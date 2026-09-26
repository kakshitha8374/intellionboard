from services.vector_store import store_chunks


test_chunks = [
    {
        "file": "README.md",
        "chunk_id": 0,
        "content": "IntelliOnboard is an AI system that helps developers understand unfamiliar GitHub repositories."
    },
    {
        "file": "main.py",
        "chunk_id": 0,
        "content": "FastAPI is used to create the backend API for IntelliOnboard."
    }
]


result = store_chunks(test_chunks)

print(result)