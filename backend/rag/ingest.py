from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.rag.loader import load_books
from backend.rag.vectorstore import QdrantVectorStore, reset_collection


BOOKS_DIR = "data/books"


def ingest_books(reset: bool = False):
    print("=" * 60)
    print("STARTING BOOK INGESTION")
    print("=" * 60)

    documents = load_books(BOOKS_DIR)
    print(f"Documents loaded: {len(documents)}")

    if not documents:
        print("No documents found.")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    print(f"Chunks created: {len(chunks)}")

    # Reset is destructive and must be explicitly requested by the caller.
    if reset:
        reset_collection()

    vectorstore = QdrantVectorStore()
    vectorstore.add_documents(chunks)

    print("=" * 60)
    print("BOOK INGESTION COMPLETE")
    print(f"Total chunks inserted: {len(chunks)}")
    print("=" * 60)


if __name__ == "__main__":
    ingest_books()
