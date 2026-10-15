from pathlib import Path

from qdrant_client.models import Filter, FieldCondition, MatchValue

from backend.rag.embeddings import MultilingualEmbeddings
from backend.rag.vectorstore import client, COLLECTION_NAME


embedding_model = MultilingualEmbeddings()


def normalize_class(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text.startswith("class"):
        text = text[5:].strip()
    return text


def normalize_subject(value):
    if value is None:
        return None

    text = str(value).strip().lower()

    aliases = {
        "math": "mathematics",
        "maths": "mathematics",
        "गणित": "mathematics",
        "english": "english",
        "hindi": "hindi",
        "punjabi": "punjabi",
        "ਪੰਜਾਬੀ": "punjabi",
        "science": "science",
        "sst": "social science",
        "social": "social science",
        "social science": "social science",
        "evs": "environmental studies",
    }
    return aliases.get(text, text)


def normalize_book(value):
    if not value:
        return None
    return Path(str(value).strip()).stem


def retrieve_context(
    query: str,
    limit: int = 5,
    class_name=None,
    subject=None,
    language=None,
    book=None,
):
    if not all(str(value or "").strip() for value in (class_name, subject, book)):
        raise ValueError("Select a class, subject and textbook first.")
    if not str(query or "").strip():
        raise ValueError("Enter a question first.")

    query_vector = embedding_model.embed_query(query)

    conditions = []

    normalized_class = normalize_class(class_name)
    normalized_subject = normalize_subject(subject)
    normalized_book = normalize_book(book)

    if normalized_class:
        conditions.append(
            FieldCondition(
                key="class",
                match=MatchValue(value=normalized_class),
            )
        )

    if normalized_subject:
        conditions.append(
            FieldCondition(
                key="subject",
                match=MatchValue(value=normalized_subject),
            )
        )

    if normalized_book:
        conditions.append(
            FieldCondition(
                key="book",
                match=MatchValue(value=normalized_book),
            )
        )

    query_filter = Filter(must=conditions) if conditions else None

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )

    return results.points


def debug_search(query, class_name=None, subject=None, book=None, limit=5):
    results = retrieve_context(
        query,
        limit=limit,
        class_name=class_name,
        subject=subject,
        book=book,
    )
    for i, point in enumerate(results, 1):
        p = point.payload or {}
        print(
            f"RESULT {i}: score={point.score:.4f} "
            f"class={p.get('class')} subject={p.get('subject')} "
            f"book={p.get('book')} page={p.get('page')}"
        )
        print((p.get("text") or "")[:500])
