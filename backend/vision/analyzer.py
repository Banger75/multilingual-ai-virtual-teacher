from __future__ import annotations

import base64
import re
from pathlib import Path

import requests

from backend.config import settings
from backend.vision.page_store import (
    build_book_page_cache,
    find_cached_page,
)


PAGE_PATTERN = re.compile(
    r"\bpage\s*(?:number\s*)?(\d+)\b",
    re.IGNORECASE,
)

VISION_PROMPT = """
Look carefully at the uploaded textbook page/image.

Focus on the picture, illustration, diagram, drawing, objects,
people, actions, and visual details that are relevant to the
student's question.

Give the answer in exactly two sections:

Picture Vocabulary:
- List the important objects, people, places, or visual items
  relevant to the picture.
- Give a short, simple description for each.

What is Happening:
- Explain the actions, events, relationships, or information
  shown visually.
- Use simple language suitable for a Class 5 student.

Do not describe unrelated page text unless it is necessary
to understand the visual content.

Do not show your reasoning.
Return only the final answer.
""".strip()


def extract_page_number(question: str) -> int | None:
    match = PAGE_PATTERN.search(question or "")

    if not match:
        return None

    return int(match.group(1))


def is_explicit_visual_question(question: str) -> bool:
    """
    Return True only when the student explicitly asks about
    a visual element.

    A page number by itself must NOT trigger vision.
    """

    text = str(question or "").strip().lower()

    if not text:
        return False

    visual_phrases = [
        "picture",
        "image",
        "illustration",
        "illustration",
        "photo",
        "photograph",
        "diagram",
        "visual",
        "drawing",
        "figure",
        "what is happening in the picture",
        "what is happening in this picture",
        "describe the picture",
        "describe this picture",
        "describe the image",
        "what do you see",
        "what can you see",
        "objects in the picture",
        "objects shown",
    ]

    return any(
        phrase in text
        for phrase in visual_phrases
    )


def _safe_book_path(book: str) -> Path:
    books_dir = Path("data/books").resolve()
    candidate = (
        books_dir /
        Path(book).name
    ).resolve()

    if candidate.parent != books_dir:
        raise ValueError(
            "Invalid textbook path."
        )

    if (
        not candidate.exists()
        or candidate.suffix.lower() != ".pdf"
    ):
        raise FileNotFoundError(
            f"Textbook not found: "
            f"{Path(book).name}"
        )

    return candidate


def _ensure_page_cache(book: str) -> dict:
    """
    Use the persistent page cache.

    Existing books uploaded before this feature may not have a cache.
    In that case we build it once automatically. New uploads already have
    their cache because the upload endpoint creates it.
    """
    cached = find_cached_page(
        book,
        1,
    )

    if cached is not None:
        # We found a valid cache file. Return metadata separately below.
        from backend.vision.page_store import load_book_page_cache

        metadata = load_book_page_cache(book)
        if metadata:
            return metadata

    return build_book_page_cache(
        Path(book).name,
        force=False,
        scale=1.5,
    )


def analyze_page_image(
    image_path: Path,
    language: str = "auto",
    question: str = "Describe the picture on this textbook page.",
) -> str:
    image_bytes = image_path.read_bytes()
    image_b64 = base64.b64encode(
        image_bytes
    ).decode("ascii")

    answer_language = {
        "en": "English",
        "english": "English",
        "hi": "Hindi",
        "hindi": "Hindi",
        "pa": "Punjabi",
        "pan": "Punjabi",
        "punjabi": "Punjabi",
    }.get(
        (language or "auto").strip().lower(),
        "the same language as the student",
    )

    prompt = (
        f"{VISION_PROMPT}\n\n"
        f"Student question: {question}\n"
        f"Answer language: {answer_language}."
    )
    mime_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(
        image_path.suffix.lower(), "image/png"
    )

    payload = {
        "model": settings.vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                f"data:{mime_type};base64,"
                                f"{image_b64}"
                            )
                        },
                    },
                ],
            }
        ],
        "temperature": settings.vision_temperature,
        "max_tokens": settings.vision_max_tokens,
    }

    response = requests.post(
        (
            f"{settings.llm_base_url.rstrip('/')}"
            "/chat/completions"
        ),
        headers={
            "Authorization":
                f"Bearer {settings.llm_api_key}"
        },
        json=payload,
        timeout=settings.vision_timeout_seconds,
    )

    response.raise_for_status()

    body = response.json()
    choices = body.get("choices") or []

    if not choices:
        raise RuntimeError(
            "Vision model returned no choices."
        )

    message = (
        choices[0].get("message")
        or {}
    )

    content = message.get(
        "content",
        "",
    )

    if isinstance(content, str):
        answer = content.strip()
    elif isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif (
                isinstance(item, dict)
                and item.get("text")
            ):
                parts.append(
                    str(item["text"])
                )

        answer = "".join(parts).strip()
    else:
        answer = str(
            content or ""
        ).strip()

    if not answer:
        raise RuntimeError(
            "Vision model returned empty content. "
            "Check that Qwen3-VL-4B is loaded in LM Studio."
        )

    return answer


def explain_book_page(
    *,
    question: str,
    book: str,
    language: str = "auto",
) -> dict:
    printed_page = extract_page_number(
        question
    )

    if printed_page is None:
        raise ValueError(
            "Please mention the printed textbook page number, "
            "for example: Explain the picture on page 13."
        )

    pdf_path = _safe_book_path(book)

    # Load the persistent cache. If this is an older book that was added
    # before page caching existed, create it once.
    metadata = _ensure_page_cache(
        pdf_path.name
    )

    page_info = None

    for page in metadata.get(
        "pages",
        [],
    ):
        if page.get(
            "printed_page"
        ) == printed_page:
            page_info = page
            break

    if page_info is None:
        # Preserve the old useful fallback for PDFs whose extracted text
        # does not expose printed page numbers.
        fallback_pdf_index = (
            printed_page - 1
        )

        pages = metadata.get(
            "pages",
            [],
        )

        if not (
            0 <= fallback_pdf_index < len(pages)
        ):
            raise ValueError(
                f"Printed page {printed_page} "
                "was not found in the textbook."
            )

        page_info = pages[
            fallback_pdf_index
        ]

    image_path = (
        Path("data/book_pages")
        / metadata["book_id"]
        / page_info["image"]
    )

    if not image_path.exists():
        # Repair a missing image without rebuilding an otherwise valid
        # cache.
        metadata = build_book_page_cache(
            pdf_path.name,
            force=True,
            scale=1.5,
        )

        page_info = next(
            (
                page
                for page in metadata.get(
                    "pages",
                    [],
                )
                if page.get(
                    "printed_page"
                ) == printed_page
            ),
            None,
        )

        if page_info is None:
            raise ValueError(
                f"Printed page {printed_page} "
                "was not found after rebuilding the page cache."
            )

        image_path = (
            Path("data/book_pages")
            / metadata["book_id"]
            / page_info["image"]
        )

    answer = analyze_page_image(
        image_path,
        language=language,
        question=question,
    )

    return {
        "success": True,
        "mode": "vision",
        "question": question,
        "book": pdf_path.name,
        "printed_page": printed_page,
        "pdf_index": page_info["pdf_index"],
        "answer": answer,
        "image_url": page_info["image_url"],
        "model": settings.vision_model,
        "page_cache": {
            "book_id": metadata["book_id"],
            "cached": True,
        },
    }
def explain_uploaded_page_text(
    *,
    image_path: Path,
    question: str,
    language: str = "auto",
) -> str:

    import pytesseract
    from PIL import Image

    image = Image.open(image_path)

    ocr_languages = {
        "en": "eng",
        "english": "eng",
        "hi": "hin",
        "hindi": "hin",
        "pa": "pan",
        "pan": "pan",
        "punjabi": "pan",
    }

    lang = ocr_languages.get(
        (language or "").strip().lower(),
        "eng",
    )

    try:
        extracted_text = pytesseract.image_to_string(
            image,
            lang=lang,
        )
    except Exception as exc:
        raise RuntimeError(
            f"OCR failed: {exc}"
        ) from exc

    extracted_text = extracted_text.strip()

    if not extracted_text:
        raise RuntimeError(
            "No readable text was found in the uploaded page."
        )

    answer_language = {
        "en": "English",
        "english": "English",
        "hi": "Hindi",
        "hindi": "Hindi",
        "pa": "Punjabi",
        "pan": "Punjabi",
        "punjabi": "Punjabi",
    }.get(
        (language or "auto").strip().lower(),
        "the same language as the student",
    )

    prompt = f"""
You are a helpful Class 5 virtual teacher.

The student uploaded a textbook page and asked:

{question}

Here is the text extracted from that page using OCR:

--- PAGE TEXT ---
{extracted_text}
--- END PAGE TEXT ---

Answer the student's question using the extracted page text.

Answer language: {answer_language}.

Use simple, clear language suitable for a Class 5 student.

Do not invent information that is not supported by the page.
Do not mention OCR unless necessary.
Do not show your reasoning.
""".strip()

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": settings.llm_temperature,
        "max_tokens": 800,
    }

    response = requests.post(
        (
            f"{settings.llm_base_url.rstrip('/')}"
            "/chat/completions"
        ),
        headers={
            "Authorization":
                f"Bearer {settings.llm_api_key}"
        },
        json=payload,
        timeout=settings.vision_timeout_seconds,
    )

    response.raise_for_status()

    body = response.json()

    choices = body.get("choices") or []

    if not choices:
        raise RuntimeError(
            "Text model returned no choices."
        )

    content = (
        choices[0]
        .get("message", {})
        .get("content", "")
    )

    if isinstance(content, str):
        answer = content.strip()
    else:
        answer = str(content or "").strip()

    if not answer:
        raise RuntimeError(
            "Text model returned an empty answer."
        )

    return answer
