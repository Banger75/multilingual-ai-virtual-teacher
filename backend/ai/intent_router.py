"""
Intent routing for the Virtual Teacher.

This router is deterministic for now.
It does not call the LLM.

It decides what kind of request the student/teacher is making so that
the application can choose the appropriate processing path.
"""

from __future__ import annotations

import re
from enum import StrEnum


class Intent(StrEnum):
    TEXT_RAG = "text_rag"
    PAGE_TEXT = "page_text"
    PAGE_VISION = "page_vision"

    UPLOADED_PAGE_TEXT = "uploaded_page_text"
    UPLOADED_PAGE_VISION = "uploaded_page_vision"

    TEXTBOOK_IMAGE_SEARCH = "textbook_image_search"
    WEB_IMAGE_SEARCH = "web_image_search"

    QUESTION_PAPER = "question_paper"
    ORAL_TEST = "oral_test"
    CLASSROOM_INTERACTION = "classroom_interaction"

    GENERAL_CHAT = "general_chat"


# ------------------------------------------------------------
# PAGE DETECTION
# ------------------------------------------------------------

PAGE_RE = re.compile(
    r"\bpage\s*(?:number\s*)?\d+\b",
    re.IGNORECASE,
)


# ------------------------------------------------------------
# VISION WORDS
# ------------------------------------------------------------

VISION_VERBS = (
    "explain",
    "describe",
    "look at",
    "what is happening",
    "what are",
    "what do you see",
    "identify",
    "analyze",
    "analyse",
)


VISUAL_NOUNS = (
    "picture",
    "image",
    "illustration",
    "photo",
    "photograph",
    "diagram",
    "visual",
)


# ------------------------------------------------------------
# UPLOADED FILE REFERENCES
# ------------------------------------------------------------

UPLOAD_PHRASES = (
    "uploaded page",
    "uploaded image",
    "uploaded picture",
    "uploaded photo",
    "this image",
    "this picture",
    "this photo",
    "this page",
)


# ------------------------------------------------------------
# IMAGE SEARCH
# ------------------------------------------------------------

IMAGE_SEARCH_PHRASES = (
    "show me a picture",
    "show me the picture",
    "show a picture",
    "find a picture",
    "find me a picture",
    "do you have a picture",
    "do you have an image",
    "find an image",
    "show me an image",
    "show me a photo",
    "find a photo",
    "show me the image",
    "find the picture",
)


# ------------------------------------------------------------
# QUESTION PAPER
# ------------------------------------------------------------

QUESTION_PAPER_PHRASES = (
    "question paper",
    "question paper from",
    "generate questions",
    "generate question",
    "generate a question paper",
    "generate mcq",
    "generate mcqs",
    "generate multiple choice",
    "generate fill in the blank",
    "generate fill in the blanks",
    "generate true false",
    "generate true/false",
    "generate short answer",
    "generate short answers",
    "generate long answer",
    "generate long answers",
    "make questions",
    "make question paper",
    "make mcq",
    "make mcqs",
    "make multiple choice",
    "make fill in the blank",
    "make fill in the blanks",
    "make true false",
    "make true/false",
    "make short answer",
    "make short answers",
    "create questions",
    "create a question paper",
    "create mcq",
    "create mcqs",
    "create multiple choice",
    "prepare questions",
    "prepare a question paper",
    "prepare a test",
    "make a test",
)

# ------------------------------------------------------------
# ORAL TEST
# ------------------------------------------------------------

ORAL_TEST_PHRASES = (
    "oral test",
    "oral exam",
    "oral examination",
    "viva",
    "viva test",
    "viva exam",
    "start oral",
    "start the oral test",
)


# ------------------------------------------------------------
# CLASSROOM / CAMERA
# ------------------------------------------------------------

CAMERA_PHRASES = (
    "camera",
    "raise hand",
    "raised hand",
    "hands raised",
    "hand raised",
    "classroom interaction",
    "classroom camera",
)


# ------------------------------------------------------------
# HELPER
# ------------------------------------------------------------

def _has_any(
    text: str,
    phrases: tuple[str, ...],
) -> bool:
    return any(
        phrase in text
        for phrase in phrases
    )


# ------------------------------------------------------------
# MAIN CLASSIFIER
# ------------------------------------------------------------


def is_question_paper_request(text: str) -> bool:
    """
    Detect question-paper / assessment-generation requests.

    This is intentionally broader than exact phrase matching because
    teachers may write:
        Generate 5 MCQs from Lesson 5
        Give me 10 true false questions
        Make 5 short answer questions
        Prepare a question paper from Lesson 5
    """

    if _has_any(text, QUESTION_PAPER_PHRASES):
        return True

    question_words = (
        "question",
        "questions",
        "mcq",
        "mcqs",
        "multiple choice",
        "fill in",
        "true false",
        "true/false",
        "short answer",
        "short answers",
        "long answer",
        "long answers",
    )

    action_words = (
        "generate",
        "make",
        "create",
        "prepare",
        "give",
        "write",
        "produce",
    )

    has_question_type = any(
        word in text
        for word in question_words
    )

    has_action = any(
        word in text
        for word in action_words
    )

    return has_question_type and has_action


def classify_intent(question: str) -> Intent:
    """
    Classify a student/teacher request.

    Examples:

        Explain the picture on page 13
            -> PAGE_VISION

        What does page 13 say?
            -> PAGE_TEXT

        Do you have a picture of Milkha Singh?
            -> TEXTBOOK_IMAGE_SEARCH

        Who was Milkha Singh?
            -> TEXT_RAG

        Generate 5 MCQs from Lesson 5
            -> QUESTION_PAPER

        Start oral test
            -> ORAL_TEST
    """

    text = " ".join(
        str(question or "")
        .strip()
        .lower()
        .split()
    )

    if not text:
        return Intent.GENERAL_CHAT

    # --------------------------------------------------------
    # ORAL TEST
    # --------------------------------------------------------

    if _has_any(
        text,
        ORAL_TEST_PHRASES,
    ):
        return Intent.ORAL_TEST

    # --------------------------------------------------------
    # CLASSROOM CAMERA
    # --------------------------------------------------------

    if _has_any(
        text,
        CAMERA_PHRASES,
    ):
        return Intent.CLASSROOM_INTERACTION

    # --------------------------------------------------------
    # QUESTION PAPER
    # --------------------------------------------------------

    if is_question_paper_request(text):
        return Intent.QUESTION_PAPER

    # --------------------------------------------------------
    # UPLOADED PAGE / IMAGE
    # --------------------------------------------------------

    if _has_any(
        text,
        UPLOAD_PHRASES,
    ):

        # Explicit visual request
        if (
            _has_any(text, VISION_VERBS)
            or _has_any(text, VISUAL_NOUNS)
        ):
            return Intent.UPLOADED_PAGE_VISION

        # Otherwise treat it as text/OCR request
        return Intent.UPLOADED_PAGE_TEXT

    # --------------------------------------------------------
    # PRINTED TEXTBOOK PAGE
    # --------------------------------------------------------

    if PAGE_RE.search(text):

        # Explicit picture/visual request
        if (
            _has_any(text, VISION_VERBS)
            and _has_any(text, VISUAL_NOUNS)
        ):
            return Intent.PAGE_VISION

        # Example:
        # "What is happening on page 13?"
        if (
            "what is happening" in text
            or "what do you see" in text
        ):
            return Intent.PAGE_VISION

        # Example:
        # "What does page 13 say?"
        # "Explain the text on page 13."
        return Intent.PAGE_TEXT

    # --------------------------------------------------------
    # IMAGE SEARCH
    # --------------------------------------------------------

    if _has_any(
        text,
        IMAGE_SEARCH_PHRASES,
    ):
        return Intent.TEXTBOOK_IMAGE_SEARCH

    # --------------------------------------------------------
    # NORMAL TEXTBOOK QUESTION
    # --------------------------------------------------------

    return Intent.TEXT_RAG