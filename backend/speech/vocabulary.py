from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from backend.config import settings


# ============================================================
# BOOK PATH / TEXT EXTRACTION
# ============================================================

BOOKS_DIR = Path("/app/data/books")


def _resolve_book_path(book: str | None) -> Path | None:
    if not book:
        return None

    raw = Path(str(book).strip())

    candidates = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(BOOKS_DIR / raw)
        candidates.append(Path("data/books") / raw)
        candidates.append(raw)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


@lru_cache(maxsize=32)
def _extract_book_text_cached(
    path_string: str,
    modified_ns: int,
) -> str:
    """Extract text from a selected PDF once and cache it."""

    path = Path(path_string)

    try:
        import pymupdf

        pdf = pymupdf.open(path)
        parts = []

        for page in pdf:
            text = page.get_text("text") or ""
            if text.strip():
                parts.append(text)

        pdf.close()
        return "\n".join(parts)

    except Exception:
        return ""


def _extract_book_text(book: str | None) -> str:
    path = _resolve_book_path(book)
    if not path:
        return ""

    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        return ""

    return _extract_book_text_cached(
        str(path),
        modified_ns,
    )


# ============================================================
# MULTILINGUAL BOOK VOCABULARY
# ============================================================


def _clean_token(token: str) -> str:
    token = token.strip(".,!?;:()[]{}\"'“”‘’…|/\\")
    return token.strip()


def _extract_vocabulary_terms(text: str, limit: int = 500) -> list[str]:
    """
    Build a compact candidate vocabulary from the selected book.

    We intentionally keep the original spelling/script from the book:
    English stays English, Hindi stays Devanagari, Punjabi stays Gurmukhi.
    """

    if not text:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = re.sub(r"\s+", " ", value).strip()
        value = value.strip("-–—•·")

        if not value:
            return

        if len(value) < 2 or len(value) > 80:
            return

        key = value.casefold()
        if key in seen:
            return

        seen.add(key)
        candidates.append(value)

    # --------------------------------------------------------
    # Glossary / New Words areas
    # --------------------------------------------------------
    vocabulary_heading = re.compile(
        r"^(new\s+words?|glossary|vocabulary|new\s+vocabulary)\b",
        re.I,
    )

    active = False
    active_lines = 0

    for line in lines:
        if vocabulary_heading.search(line):
            active = True
            active_lines = 0
            continue

        if active:
            # Vocabulary blocks are normally short. Stop after a reasonable
            # amount of text so we do not accidentally collect whole lessons.
            active_lines += 1
            if active_lines > 35:
                active = False
            else:
                # Keep the first phrase/word from each glossary-like line.
                pieces = re.split(r"\s{2,}|\t|[|]", line)
                for piece in pieces[:3]:
                    cleaned = _clean_token(piece)
                    if 2 <= len(cleaned) <= 60:
                        add(cleaned)

    # --------------------------------------------------------
    # Capitalized / named terms in Latin text.
    # --------------------------------------------------------
    for match in re.finditer(
        r"\b(?:[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'-]+(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'-]+){1,3})\b",
        text,
    ):
        add(match.group(0))

    # --------------------------------------------------------
    # General multilingual word-frequency candidates.
    # This also works for Devanagari and Gurmukhi because Python regex
    # \w is Unicode-aware.
    # --------------------------------------------------------
    words = [
        _clean_token(word)
        for word in re.findall(r"[\w\u0900-\u097F\u0A00-\u0A7F'-]+", text, re.UNICODE)
    ]

    counts = Counter(
        word
        for word in words
        if len(word) >= 3
    )

    for word, _count in counts.most_common(limit):
        add(word)
        if len(candidates) >= limit:
            break

    return candidates[:limit]


@lru_cache(maxsize=32)
def _book_vocabulary_cached(
    book_path: str,
    modified_ns: int,
) -> tuple[str, ...]:
    text = _extract_book_text_cached(
        book_path,
        modified_ns,
    )
    return tuple(_extract_vocabulary_terms(text))


def get_book_vocabulary(book: str | None) -> list[str]:
    path = _resolve_book_path(book)
    if not path:
        return []

    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        return []

    return list(
        _book_vocabulary_cached(
            str(path),
            modified_ns,
        )
    )


# ============================================================
# FAST SAME-SCRIPT CORRECTION
# ============================================================


def _normalise_for_match(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^\w\u0900-\u097F\u0A00-\u0A7F ]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _same_script_fuzzy_corrections(
    question: str,
    candidates: list[str],
) -> tuple[str, list[dict]]:
    """
    Correct only high-confidence close spellings.

    We only touch candidates of at least 4 characters and require a
    strong similarity score. This prevents ordinary student words from
    being replaced aggressively.
    """

    if not question or not candidates:
        return question, []

    result = question
    corrections: list[dict] = []

    # Longest candidates first, especially useful for names such as
    # "Milkha Singh".
    candidates = sorted(
        candidates,
        key=lambda value: len(_normalise_for_match(value)),
        reverse=True,
    )

    for candidate in candidates:
        normalized_candidate = _normalise_for_match(candidate)
        if len(normalized_candidate) < 4:
            continue

        # Only compare candidates that share at least one script family.
        candidate_latin = bool(re.search(r"[A-Za-z]", candidate))
        candidate_deva = bool(re.search(r"[\u0900-\u097F]", candidate))
        candidate_gurmukhi = bool(re.search(r"[\u0A00-\u0A7F]", candidate))

        words = normalized_candidate.split()
        n = len(words)

        token_pattern = r"[\w\u0900-\u097F\u0A00-\u0A7F'-]+"
        tokens = list(re.finditer(token_pattern, result, re.UNICODE))

        for index in range(len(tokens)):
            end_index = min(len(tokens), index + n)
            if end_index - index != n:
                continue

            span = result[tokens[index].start():tokens[end_index - 1].end()]
            normalized_span = _normalise_for_match(span)

            if len(normalized_span) < 4:
                continue

            span_latin = bool(re.search(r"[A-Za-z]", span))
            span_deva = bool(re.search(r"[\u0900-\u097F]", span))
            span_gurmukhi = bool(re.search(r"[\u0A00-\u0A7F]", span))

            if candidate_latin != span_latin:
                continue
            if candidate_deva != span_deva:
                continue
            if candidate_gurmukhi != span_gurmukhi:
                continue

            score = SequenceMatcher(
                None,
                normalized_span,
                normalized_candidate,
            ).ratio()

            # Strong threshold for automatic correction.
            threshold = 0.92 if n == 1 else 0.86

            if score < threshold or normalized_span == normalized_candidate:
                continue

            result = (
                result[:tokens[index].start()]
                + candidate
                + result[tokens[end_index - 1].end():]
            )

            corrections.append(
                {
                    "from": span,
                    "to": candidate,
                    "method": "book_fuzzy_match",
                    "score": round(score, 3),
                }
            )
            break

    return result, corrections


# ============================================================
# LLM-ASSISTED MULTILINGUAL CORRECTION
# ============================================================


def _response_text(response) -> str:
    content = getattr(response, "content", "")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "".join(parts).strip()

    return str(content or "").strip()


def _clean_corrected_question(value: str, original: str) -> str:
    value = value.strip()

    # Remove common wrappers from a small local model response.
    value = re.sub(r"^```(?:text|json)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*```$", "", value)
    value = value.strip().strip('"').strip("'").strip()

    if not value or value.upper() in {
        "NO_CHANGE",
        "NO CHANGE",
        "UNCHANGED",
    }:
        return original

    # Never allow the correction model to return a paragraph.
    value = value.splitlines()[0].strip()

    return value or original


def _llm_correct_question(
    question: str,
    book: str | None,
    language: str,
    candidates: list[str],
) -> tuple[str, dict | None]:
    """
    Use the same local Qwen text model to correct Whisper errors using
    only the selected textbook's vocabulary.

    The model is explicitly told not to answer the question. It only
    repairs likely recognition errors.
    """

    if not question.strip() or not candidates:
        return question, None

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        correction_model = ChatOpenAI(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            temperature=0,
            max_tokens=120,
        )

        language_name = {
            "en": "English",
            "english": "English",
            "hi": "Hindi",
            "hindi": "Hindi",
            "pa": "Punjabi",
            "punjabi": "Punjabi",
            "pan": "Punjabi",
            "auto": "the student's detected language",
        }.get((language or "auto").lower(), language or "the student's language")

        candidate_text = "\n".join(
            f"- {candidate}" for candidate in candidates[:500]
        )

        prompt = f"""
You are a speech-recognition correction layer for a Class 5 virtual teacher.

Selected textbook: {book or 'unknown'}
Student speech language: {language_name}

Whisper transcription:
{question}

IMPORTANT:
- Do NOT answer the student's question.
- Do NOT translate the question.
- Keep the student's language and sentence structure.
- Correct only likely speech-recognition/spelling mistakes.
- Use the selected textbook vocabulary below as the authority for names,
  places, lesson terms, and difficult textbook words.
- If a word sounds like a textbook term, restore the exact spelling/script
  used in the book.
- If you are not confident, leave the original wording unchanged.
- Do not invent a textbook term.
- Return ONLY the corrected question on one line.
- If no correction is needed, return NO_CHANGE.

TEXTBOOK VOCABULARY:
{candidate_text}

Corrected question:
/no_think
""".strip()

        response = correction_model.invoke(
            [
                SystemMessage(
                    content=(
                        "You correct speech recognition only. "
                        "You never answer the question."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )

        corrected = _clean_corrected_question(
            _response_text(response),
            question,
        )

        if corrected == question:
            return question, None

        return corrected, {
            "method": "local_qwen_textbook_correction",
            "book": book,
            "language": language,
        }

    except Exception as exc:
        # Speech must remain usable even if the optional correction pass
        # fails. The original Whisper transcription is always safe fallback.
        print(f"Speech vocabulary correction warning: {exc}")
        return question, None


# ============================================================
# PUBLIC NORMALIZER
# ============================================================


def normalize_spoken_question(
    question: str,
    *,
    class_name=None,
    subject=None,
    book=None,
    language="auto",
) -> tuple[str, dict]:
    """
    Improve a Whisper transcript using the selected textbook.

    Returns:
        (corrected_question, diagnostic_info)

    The correction is deliberately conservative:
      1. High-confidence same-script fuzzy correction.
      2. Local Qwen textbook-aware multilingual correction.
      3. Original Whisper text as the guaranteed fallback.
    """

    original = (question or "").strip()

    if not original:
        return "", {
            "changed": False,
            "method": "none",
            "book": book,
            "language": language,
        }

    candidates = get_book_vocabulary(book)

    # If the PDF is unavailable inside the container, use Qdrant context
    # as a fallback vocabulary source.
    if not candidates:
        try:
            from backend.rag.retriever import retrieve_context

            results = retrieve_context(
                original,
                limit=8,
                class_name=class_name,
                subject=subject,
                book=book,
            )

            context = "\n".join(
                str((result.payload or {}).get("text", ""))
                for result in results
            )

            candidates = _extract_vocabulary_terms(context, limit=350)
        except Exception as exc:
            print(f"Speech vocabulary retrieval warning: {exc}")

    corrected, fuzzy_changes = _same_script_fuzzy_corrections(
        original,
        candidates,
    )

    # Let Qwen handle multilingual/transliteration cases and cases where
    # fuzzy matching alone did not produce a correction.
    if not fuzzy_changes:
        corrected_by_llm, llm_change = _llm_correct_question(
            corrected,
            book,
            language,
            candidates,
        )

        if corrected_by_llm != corrected:
            corrected = corrected_by_llm
            return corrected, {
                "changed": True,
                "method": "local_qwen_textbook_correction",
                "corrections": [llm_change] if llm_change else [],
                "book": book,
                "language": language,
            }

    return corrected, {
        "changed": corrected != original,
        "method": "book_fuzzy_match" if fuzzy_changes else "unchanged",
        "corrections": fuzzy_changes,
        "book": book,
        "language": language,
        "vocabulary_size": len(candidates),
    }
