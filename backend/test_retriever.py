from services.retriever import search_repository


question = "What is IntelliOnboard?"

results = search_repository(question)


for result in results:
    print("\n----------------------")
    print("File:", result["file"])
    print("Chunk:", result["chunk_id"])
    print("Distance:", result["distance"])
    print("Content:", result["content"])