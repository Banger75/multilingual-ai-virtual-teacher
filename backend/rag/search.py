from backend.rag.retriever import retrieve_context


def search(
    query: str,
    limit: int = 5,
    book_id: str | None = None,
    subject: str | None = None,
    class_level: str | None = None,
):
    return retrieve_context(
        query,
        limit=limit,
        class_name=class_level,
        subject=subject,
        book=book_id,
    )


if __name__ == "__main__":
    question = input("Ask a question about the textbook: ")
    results = search(question)
    print("\n========== RESULTS ==========\n")
    for i, result in enumerate(results, 1):
        payload = result.payload or {}
        print(f"--- Result {i} ---")
        print(payload.get("text", ""))
        print("Book:", payload.get("book"))
        print("Subject:", payload.get("subject"))
        print("Class:", payload.get("class"))
        print("Page:", payload.get("page"))
        print("Score:", result.score)
