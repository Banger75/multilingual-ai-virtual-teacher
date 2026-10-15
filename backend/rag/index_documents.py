from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.rag.loader import load_book, load_books
from backend.rag.vectorstore import QdrantVectorStore, reset_collection


def index_book(path, metadata=None):
    """Append one uploaded textbook without resetting existing textbook data."""
    documents = load_book(path, metadata_override=metadata)
    if not documents:
        raise ValueError("No readable textbook content was found; check the PDF/OCR languages.")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    QdrantVectorStore().add_documents(chunks)
    return len(chunks)


def index_books(reset: bool = False):
    documents = load_books("data/books")
    if not documents:
        print("No documents found.")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    if reset:
        reset_collection()
    QdrantVectorStore().add_documents(chunks)
    print(f"Indexed {len(chunks)} chunks.")


if __name__ == "__main__":
    index_books()
