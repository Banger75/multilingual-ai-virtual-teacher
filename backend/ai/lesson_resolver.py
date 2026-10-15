"""
Lesson resolver for the Virtual Teacher.

This module identifies a lesson from the existing Qdrant textbook
pages without depending on printed textbook page numbers.

The Qdrant `page` field is used only as an internal PDF ordering
mechanism.

Example:

    Lesson 5: Raja Birbal
        ↓
    PDF page 64
        ↓
    all following pages
        ↓
    Lesson 6: Bank-Our Need
        ↓
    PDF page 77

Therefore Lesson 5 consists of the content between those two
lesson boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from qdrant_client.models import Filter, FieldCondition, MatchValue

from backend.rag.retriever import (
    normalize_class,
    normalize_subject,
)
from backend.rag.vectorstore import (
    client,
    COLLECTION_NAME,
)


# ============================================================
# DATA STRUCTURE
# ============================================================


@dataclass
class LessonInfo:
    lesson_number: int
    title: str
    start_pdf_page: int
    end_pdf_page: int | None = None


# ============================================================
# LESSON HEADING PATTERNS
# ============================================================

LESSON_HEADING_RE = re.compile(
    r"""
    (?im)
    ^\s*
    (?:
        lesson
        |
        chapter
    )
    \s*
    (\d{1,2})
    \s*
    (?:
        [:\-–—.]
        \s*
    )?
    (.*?)
    \s*$
    """,
    re.VERBOSE,
)


# Also handles cases such as:

# Lesson 5
# Raja Birbal

# The first regex catches "Lesson 5".
# This helper searches nearby text for a title.


def _normalise_title(text: str) -> str:
    text = str(text or "")

    text = text.replace("\x00", " ")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip(" :-–—\n\t")


# ============================================================
# LOAD ALL BOOK PAGES
# ============================================================


def _load_book_pages(
    class_name=None,
    subject=None,
    book=None,
) -> list[dict]:
    """
    Load all indexed pages for one textbook.

    We intentionally use Qdrant scroll rather than semantic search.

    Semantic search is good for answering questions.

    It is NOT reliable for finding every page belonging to a lesson.
    """

    if not all(str(value or "").strip() for value in (class_name, subject, book)):
        raise ValueError("Select a class, subject and textbook first.")

    conditions = []

    normalized_class = normalize_class(
        class_name
    )

    normalized_subject = normalize_subject(
        subject
    )

    if normalized_class:

        conditions.append(
            FieldCondition(
                key="class",
                match=MatchValue(
                    value=normalized_class
                ),
            )
        )

    if normalized_subject:

        conditions.append(
            FieldCondition(
                key="subject",
                match=MatchValue(
                    value=normalized_subject
                ),
            )
        )

    if book:

        # Existing Qdrant metadata stores
        # the filename stem in "book".
        from pathlib import Path

        normalized_book = Path(
            str(book).strip()
        ).stem

        conditions.append(
            FieldCondition(
                key="book",
                match=MatchValue(
                    value=normalized_book
                ),
            )
        )

    query_filter = (
        Filter(must=conditions)
        if conditions
        else None
    )

    pages = []

    offset = None

    while True:

        records, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=query_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for record in records:

            payload = record.payload or {}

            text = str(
                payload.get("text")
                or ""
            ).strip()

            page = payload.get("page")

            if not text:
                continue

            try:
                page_number = int(page)
            except (
                TypeError,
                ValueError,
            ):
                continue

            pages.append(
                {
                    "page": page_number,
                    "text": text,
                    "payload": payload,
                }
            )

        if next_offset is None:
            break

        offset = next_offset

    # --------------------------------------------------------
    # Sort by INTERNAL PDF page number.
    # --------------------------------------------------------

    pages.sort(
        key=lambda item: item["page"]
    )

    # --------------------------------------------------------
    # Remove duplicate page records.
    #
    # Some existing searches showed duplicate page numbers.
    # We don't want the same page twice in lesson content.
    # --------------------------------------------------------

    unique_pages = []

    seen_chunks = set()

    for item in pages:

        page_number = item["page"]

        chunk_key = (page_number, item["text"])
        if chunk_key in seen_chunks:
            continue

        seen_chunks.add(chunk_key)

        unique_pages.append(item)

    # Keep all distinct chunks on a page; dropping by page loses evidence.
    grouped = {}
    for item in unique_pages:
        if item["page"] not in grouped:
            grouped[item["page"]] = dict(item)
        else:
            grouped[item["page"]]["text"] += "\n\n" + item["text"]
    return list(grouped.values())


# ============================================================
# FIND LESSON HEADINGS
# ============================================================
def _find_lesson_headings(
    pages: list[dict],
) -> list[LessonInfo]:
    """
    Find actual lesson/chapter headings.

    Important:
    Textbooks often contain a Table of Contents where many lesson
    headings appear on the same PDF page.

    Example:

        Lesson 1: ...
        Lesson 2: ...
        Lesson 3: ...
        ...
        Lesson 9: ...

    We must NOT treat those TOC entries as actual lesson starts.

    A normal lesson-start page usually contains only one lesson
    heading, so pages containing multiple lesson headings are treated
    as TOC/index pages and ignored.
    """

    headings = []

    for index, page in enumerate(pages):

        text = page["text"]

        matches = list(
            LESSON_HEADING_RE.finditer(
                text
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Multiple lesson headings on one page normally means
        # this is the Table of Contents.
        #
        # Do not treat those entries as lesson boundaries.
        # ----------------------------------------------------

        if len(matches) > 1:
            continue

        if not matches:
            continue

        match = matches[0]

        lesson_number = int(
            match.group(1)
        )

        title = _normalise_title(
            match.group(2)
        )

        # ----------------------------------------------------
        # Some PDFs put the title on the next line.
        #
        # Example:
        #
        # Lesson 5
        # Raja Birbal
        #
        # Instead of:
        #
        # Lesson 5: Raja Birbal
        # ----------------------------------------------------

        if not title:

            lines = text.splitlines()

            for line_index, line in enumerate(
                lines
            ):

                if re.fullmatch(
                    rf"\s*(?:Lesson|Chapter)\s*{lesson_number}\s*",
                    line,
                    flags=re.I,
                ):

                    for next_line in lines[
                        line_index + 1 :
                    ]:

                        candidate = _normalise_title(
                            next_line
                        )

                        if not candidate:
                            continue

                        # Ignore common metadata headings.
                        if candidate.lower() in {
                            "objectives",
                            "objective",
                            "new words",
                            "pre reading",
                            "content",
                        }:
                            continue

                        title = candidate

                        break

                    break

        headings.append(
            LessonInfo(
                lesson_number=lesson_number,
                title=title,
                start_pdf_page=page["page"],
            )
        )

    # --------------------------------------------------------
    # Remove duplicate lesson headings.
    #
    # Keep the first actual occurrence of each lesson number.
    # --------------------------------------------------------

    unique_by_lesson = {}

    for heading in headings:

        lesson_number = heading.lesson_number

        if lesson_number not in unique_by_lesson:

            unique_by_lesson[
                lesson_number
            ] = heading

    headings = list(
        unique_by_lesson.values()
    )

    # --------------------------------------------------------
    # Sort by PDF page.
    # --------------------------------------------------------

    headings.sort(
        key=lambda item: item.start_pdf_page
    )

    # --------------------------------------------------------
    # Determine the end page.
    #
    # Lesson N ends immediately before Lesson N+1.
    # --------------------------------------------------------

    for index, heading in enumerate(
        headings
    ):

        if index + 1 < len(headings):

            next_heading = headings[
                index + 1
            ]

            heading.end_pdf_page = (
                next_heading.start_pdf_page - 1
            )

        else:

            # Last lesson continues to the end
            # of the indexed textbook.
            heading.end_pdf_page = None

    return headings



# ============================================================
# RESOLVE LESSON
# ============================================================


def resolve_lesson(
    lesson_number: int,
    class_name=None,
    subject=None,
    book=None,
) -> LessonInfo | None:
    """
    Resolve a lesson number to its actual PDF page range.

    Printed textbook page numbers are NOT required.
    """

    pages = _load_book_pages(
        class_name=class_name,
        subject=subject,
        book=book,
    )

    if not pages:
        return None

    headings = _find_lesson_headings(
        pages
    )

    for heading in headings:

        if (
            heading.lesson_number
            == int(lesson_number)
        ):

            return heading

    return None


# ============================================================
# GET LESSON CONTENT
# ============================================================


def get_lesson_content(
    lesson_number: int,
    class_name=None,
    subject=None,
    book=None,
) -> dict | None:
    """
    Return all indexed textbook content belonging to a lesson.
    """

    pages = _load_book_pages(
        class_name=class_name,
        subject=subject,
        book=book,
    )

    if not pages:
        return None

    headings = _find_lesson_headings(
        pages
    )

    target = None

    for heading in headings:

        if (
            heading.lesson_number
            == int(lesson_number)
        ):

            target = heading
            break

    if target is None:
        return None

    start_page = (
        target.start_pdf_page
    )

    end_page = (
        target.end_pdf_page
    )

    lesson_pages = []

    for page in pages:

        page_number = page["page"]

        if page_number < start_page:
            continue

        if (
            end_page is not None
            and page_number > end_page
        ):
            continue

        lesson_pages.append(
            page
        )

    content_parts = []

    for page in lesson_pages:

        content_parts.append(
            page["text"]
        )

    content = "\n\n".join(
        content_parts
    ).strip()

    return {
        "lesson_number": target.lesson_number,
        "title": target.title,
        "start_pdf_page": start_page,
        "end_pdf_page": end_page,
        "page_count": len(lesson_pages),
        "content": content,
    }


# ============================================================
# LIST LESSONS
# ============================================================


def list_lessons(
    class_name=None,
    subject=None,
    book=None,
) -> list[LessonInfo]:
    """
    Return all detected lessons in a textbook.
    """

    pages = _load_book_pages(
        class_name=class_name,
        subject=subject,
        book=book,
    )

    return _find_lesson_headings(
        pages
    )
