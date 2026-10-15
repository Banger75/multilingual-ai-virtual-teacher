from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from qdrant_client.models import Filter, FieldCondition, MatchValue

from backend.config import settings
from backend.rag.embeddings import MultilingualEmbeddings


QDRANT_URL = settings.qdrant_url
COLLECTION_NAME = settings.qdrant_collection

client = QdrantClient(url=QDRANT_URL)
embedding_model = MultilingualEmbeddings()


def get_embedding_dimension() -> int:
    return len(embedding_model.embed_query("test embedding"))


def collection_exists() -> bool:
    return COLLECTION_NAME in {
        c.name for c in client.get_collections().collections
    }


def create_collection_if_not_exists() -> None:
    dimension = get_embedding_dimension()

    if not collection_exists():
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance.COSINE,
            ),
        )
        print(f"Created Qdrant collection {COLLECTION_NAME} ({dimension} dimensions)")
        return

    info = client.get_collection(COLLECTION_NAME)
    configured = info.config.params.vectors
    existing_size = getattr(configured, "size", None)

    if existing_size != dimension:
        raise RuntimeError(
            f"Qdrant collection '{COLLECTION_NAME}' has vector size "
            f"{existing_size}, but the configured embedding model produces "
            f"{dimension}. Delete/recreate the collection and re-index the books."
        )


def reset_collection() -> None:
    if collection_exists():
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted Qdrant collection: {COLLECTION_NAME}")
    create_collection_if_not_exists()


class QdrantVectorStore:
    def __init__(self):
        create_collection_if_not_exists()

    def add_documents(self, documents, batch_size: int = 32):
        if batch_size < 1:
            raise ValueError("Batch size must be positive.")
        # Append safely, including collections previously indexed with random IDs.
        # Never delete a collection merely to avoid duplicate chunks.
        existing_by_book = {}
        pending = []
        for document in documents:
            metadata = document.metadata
            scope = tuple(str(metadata.get(key) or "").strip() for key in ("class", "subject", "book"))
            if not all(scope):
                raise ValueError("Indexed documents need class, subject and book metadata.")
            if scope not in existing_by_book:
                seen = set()
                offset = None
                while True:
                    records, offset = client.scroll(
                        collection_name=COLLECTION_NAME,
                        scroll_filter=Filter(must=[
                            FieldCondition(key=key, match=MatchValue(value=value))
                            for key, value in zip(("class", "subject", "book"), scope)
                        ]),
                        limit=256, offset=offset, with_vectors=False,
                        with_payload=["page", "text"],
                    )
                    for record in records:
                        payload = record.payload or {}
                        seen.add((str(payload.get("page")), payload.get("text", "")))
                    if offset is None:
                        break
                existing_by_book[scope] = seen
            key = (str(metadata.get("page")), document.page_content)
            if key not in existing_by_book[scope]:
                existing_by_book[scope].add(key)
                pending.append(document)
        documents = pending
        total = len(documents)
        for start in range(0, total, batch_size):
            batch = documents[start:start + batch_size]
            texts = [doc.page_content for doc in batch]
            vectors = embedding_model.embed_documents(texts)

            from uuid import uuid4
            from qdrant_client.models import PointStruct

            points = []
            for document, vector in zip(batch, vectors):
                payload = {
                    "text": document.page_content,
                    **document.metadata,
                }
                points.append(
                    PointStruct(
                        id=str(uuid4()),
                        vector=vector,
                        payload=payload,
                    )
                )

            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True,
            )

        print(f"Inserted {total} chunks into Qdrant.")
