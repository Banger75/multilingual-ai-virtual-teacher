"""
Oral Test Question Bank
=======================

Creates a reusable, textbook-grounded question bank for the
Virtual Teacher Oral Test.

Flow:

    Selected Lesson
          ↓
    lesson_resolver
          ↓
    Complete lesson content
          ↓
    Qwen
          ↓
    Question Bank
          ↓
    Deterministic validation
          ↓
    Easy / Medium / Hard questions

This module is intentionally separate from question_generator.py
so the existing written Question Paper feature is not affected.
"""

from __future__ import annotations

import json
import math
import random
import re
import unicodedata
from typing import Any

from langchain_openai import ChatOpenAI

from backend.config import settings
from backend.ai.lesson_resolver import get_lesson_content


# ============================================================
# CONFIGURATION
# ============================================================

MAX_LESSON_CHARS = 25000

# Number of times Qwen can retry after validation failure.
MAX_GENERATION_ATTEMPTS = 3

# Default question-bank size.
DEFAULT_QUESTION_COUNT = 30


# ============================================================
# LLM
# ============================================================

question_bank_llm = ChatOpenAI(
    model=settings.llm_model,
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    temperature=0.35,
    max_tokens=5000,
    extra_body={
        "Chat_templete_kwargs": {
            "enable_thinking": False
        }
    },
)


# ============================================================
# TEXT HELPERS
# ============================================================

def _normalize_text(text: Any) -> str:
    """
    Normalize textbook/LLM text for robust comparison.

    PDF extraction can introduce:
    - different quotation marks
    - unusual apostrophes
    - line breaks
    - multiple spaces
    - ligatures
    - punctuation differences

    We normalize these differences without changing the
    actual words.
    """

    text = str(text or "").lower()

    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",

        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',

        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",

        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "st",
        "\ufb06": "st",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Normalize whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _clean_json_text(text: str) -> str:
    """
    Remove markdown code fences from an LLM response.
    """

    text = str(text or "").strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()


def _extract_json(text: str) -> dict:
    """
    Extract a JSON object from the LLM response.
    """

    cleaned = _clean_json_text(text)

    try:
        value = json.loads(cleaned)

        if isinstance(value, dict):
            return value

    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start >= 0 and end > start:

        candidate = cleaned[
            start:end + 1
        ]

        try:
            value = json.loads(candidate)

            if isinstance(value, dict):
                return value

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "Question bank generator returned invalid JSON."
    )


# ============================================================
# EVIDENCE VALIDATION
# ============================================================

def _evidence_exists(
    evidence: str,
    lesson_content: str,
) -> bool:
    """
    Verify that the evidence actually occurs in the textbook.

    Strong matching is preferred because evidence is supposed
    to be copied from the lesson.
    """

    evidence_text = _normalize_text(
        evidence
    )

    lesson_text = _normalize_text(
        lesson_content
    )

    if not evidence_text:
        return False

    if not lesson_text:
        return False

    # Exact normalized evidence.
    if evidence_text in lesson_text:
        return True

    # Every supplied sentence must be present, including short ones.
    # A majority match could otherwise hide invented answer evidence.
    sentences = [part.strip() for part in re.split(r"[.!?।]+", evidence_text) if part.strip()]
    return bool(sentences) and all(sentence in lesson_text for sentence in sentences)


def _meaningful_words(text: str) -> list[str]:
    # Python's \w excludes combining vowel marks used by Hindi and Punjabi.
    words = "".join(
        character if unicodedata.category(character)[0] in {"L", "M", "N"} else " "
        for character in text
    ).split()
    return [word for word in words if len(word) >= 3]


def _answer_supported(
    answer: str,
    evidence: str,
) -> bool:
    """
    Check whether the answer is reasonably supported by
    the supplied textbook evidence.
    """

    answer_text = _normalize_text(
        answer
    )

    evidence_text = _normalize_text(
        evidence
    )

    if not answer_text or not evidence_text:
        return False

    # Best case.
    if re.search(r"(?<!\w)" + re.escape(answer_text) + r"(?!\w)", evidence_text):
        return True

    # Numeric answers.
    if re.fullmatch(
        r"\d+",
        answer_text,
    ):
        return False

    answer_words = _meaningful_words(answer_text)

    if not answer_words:
        return False

    evidence_words = set(_meaningful_words(evidence_text))
    matched = sum(
            1
            for word in answer_words
            if word in evidence_words
        )

    required = max(
            2,
            math.ceil(len(answer_words) * 0.80),
        )

    return matched >= required


# ============================================================
# DUPLICATE DETECTION
# ============================================================

def _question_key(question: str) -> str:
    """
    Create a normalized key for duplicate detection.
    """

    text = _normalize_text(
        question
    )

    # Retain letters and combining vowel marks in Hindi and Punjabi.
    text = "".join(
        character for character in text
        if not unicodedata.category(character).startswith(("P", "S"))
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# BUILD PROMPT
# ============================================================

def _build_prompt(
    lesson_content: str,
    lesson_number: int,
    lesson_title: str,
    language: str,
    question_count: int,
    previous_error: str | None = None,
) -> str:

    answer_language = (
        language
        if language
        and language.lower()
        not in {
            "auto",
            "same",
        }
        else "the same language as the textbook"
    )

    retry_instruction = ""

    if previous_error:

        retry_instruction = f"""
============================================================
PREVIOUS GENERATION FAILED
============================================================

The previous question bank failed validation.

Reason:

{previous_error}

You MUST correct the problem.

Do not repeat the invalid question.
Generate a completely new question bank.

============================================================
"""

    return f"""
/no_think

You are an experienced school teacher creating an
ORAL TEST question bank for students.

Your ONLY source of knowledge is the supplied textbook lesson.

Do NOT use:
- general knowledge
- internet knowledge
- model memory
- facts from another lesson
- facts from another textbook
- assumptions
- invented information
- invented morals
- invented conclusions

{retry_instruction}

============================================================
LESSON
============================================================

Lesson number:
{lesson_number}

Lesson title:
{lesson_title}

Question language:
{answer_language}

============================================================
QUESTION BANK
============================================================

Generate exactly:

{question_count}

questions.

Difficulty distribution:

- Easy: approximately 40%
- Medium: approximately 40%
- Hard: approximately 20%

Every question must be suitable for an oral test.

============================================================
IMPORTANT ORAL TEST RULES
============================================================

1. Every question MUST be answerable from the textbook lesson.

2. Every answer MUST be directly supported by the lesson.

3. Do not ask personal-opinion questions.

4. Do not ask questions about morals unless the textbook
   explicitly states the moral.

5. Do not ask questions requiring outside knowledge.

6. Questions should be phrased naturally for a teacher
   speaking to a student.

7. Do NOT simply copy textbook exercise questions.

8. Rephrase textbook information into new questions.

9. Avoid duplicate questions.

10. Each question must have one clear expected answer.

11. Keep questions appropriate for the student's class.

12. Hard questions should require understanding or combining
    information from the lesson, but must still be completely
    supported by the textbook.

13. Every question MUST contain exact textbook evidence.

14. Evidence must be copied from the supplied lesson.

15. Do NOT summarize or invent evidence.

============================================================
DIFFICULTY
============================================================

Easy:
Directly asks for an explicitly stated fact.

Example:
"What was the original name of Raja Birbal?"

Medium:
Requires understanding or connecting two nearby facts.

Example:
"How did Birbal's action change the appearance of Akbar's line?"

Hard:
Requires combining information from different parts of the
lesson, while still having a clear textbook-supported answer.

Do NOT make hard questions dependent on outside knowledge.

============================================================
REQUIRED JSON
============================================================

{{
  "questions": [
    {{
      "question_id": "Q001",
      "question": "Question text",
      "answer": "Expected answer",
      "difficulty": "easy",
      "evidence": "Exact text copied from the textbook"
    }}
  ]
}}

Difficulty MUST be one of:

"easy"
"medium"
"hard"

============================================================
TEXTBOOK LESSON
============================================================

{lesson_content}

============================================================
END TEXTBOOK LESSON
============================================================

Generate EXACTLY {question_count} questions.

Return ONLY valid JSON.
"""


# ============================================================
# VALIDATE QUESTION BANK
# ============================================================

def _validate_question_bank(
    data: dict,
    lesson_content: str,
    expected_count: int,
) -> dict:

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Question bank response is not an object."
        )

    questions = data.get(
        "questions",
        [],
    )

    if not isinstance(
        questions,
        list,
    ):
        raise ValueError(
            "Question bank 'questions' must be a list."
        )

    if len(questions) != expected_count:
        raise ValueError(
            f"Expected {expected_count} questions, "
            f"but received {len(questions)}."
        )

    seen = set()

    valid_difficulties = {
        "easy",
        "medium",
        "hard",
    }

    for index, item in enumerate(
        questions,
        1,
    ):

        if not isinstance(
            item,
            dict,
        ):
            raise ValueError(
                f"Question {index} is invalid."
            )

        question = str(
            item.get("question") or ""
        ).strip()

        answer = str(
            item.get("answer") or ""
        ).strip()

        evidence = str(
            item.get("evidence") or ""
        ).strip()

        difficulty = str(
            item.get("difficulty") or ""
        ).strip().lower()

        if not question:
            raise ValueError(
                f"Question {index} has no question."
            )

        if not answer:
            raise ValueError(
                f"Question {index} has no answer."
            )

        if not evidence:
            raise ValueError(
                f"Question {index} has no evidence."
            )

        if difficulty not in valid_difficulties:
            raise ValueError(
                f"Question {index} has invalid "
                f"difficulty: {difficulty}"
            )

        key = _question_key(
            question
        )

        if key in seen:
            raise ValueError(
                f"Duplicate question detected: "
                f"{question}"
            )

        seen.add(key)

        # ----------------------------------------------------
        # Evidence must actually exist in lesson.
        # ----------------------------------------------------

        if not _evidence_exists(
            evidence,
            lesson_content,
        ):
            raise ValueError(
                f"Question {index} evidence is not "
                f"present in the textbook.\n"
                f"Evidence: {evidence}"
            )

        # ----------------------------------------------------
        # Answer must be supported by evidence.
        # ----------------------------------------------------

        if not _answer_supported(
            answer,
            evidence,
        ):
            raise ValueError(
                f"Question {index} answer is not "
                f"supported by its evidence.\n"
                f"Answer: {answer}\n"
                f"Evidence: {evidence}"
            )

        item["question_id"] = (
            str(
                item.get("question_id")
                or f"Q{index:03d}"
            ).strip()
        )

        item["question"] = question
        item["answer"] = answer
        item["difficulty"] = difficulty
        item["evidence"] = evidence

    return data


# ============================================================
# REMOVE INTERNAL EVIDENCE
# ============================================================

def _remove_evidence(
    data: dict,
) -> dict:
    """
    Evidence is required internally for validation but should
    not normally be shown to the student.
    """

    questions = data.get(
        "questions",
        [],
    )

    for item in questions:

        if isinstance(
            item,
            dict,
        ):
            item.pop(
                "evidence",
                None,
            )

    return data


# ============================================================
# GENERATE QUESTION BANK
# ============================================================

def generate_question_bank(
    lesson_number: int,
    class_name=None,
    subject=None,
    book=None,
    language="auto",
    question_count: int = DEFAULT_QUESTION_COUNT,
) -> dict:
    """
    Generate a textbook-grounded oral-test question bank.

    Example:

        generate_question_bank(
            lesson_number=5,
            class_name="5",
            subject="English",
            book="English_Class 5.pdf",
            language="English",
            question_count=30,
        )
    """

    try:
        lesson_number = int(
            lesson_number
        )
    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Lesson number must be an integer."
        )

    try:
        question_count = int(
            question_count
        )
    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Question count must be an integer."
        )

    if lesson_number <= 0:
        raise ValueError(
            "Lesson number must be greater than zero."
        )

    if question_count <= 0:
        raise ValueError(
            "Question count must be greater than zero."
        )

    if question_count > 100:
        raise ValueError(
            "Question count cannot exceed 100."
        )

    # --------------------------------------------------------
    # Get complete lesson.
    # --------------------------------------------------------

    lesson = get_lesson_content(
        lesson_number=lesson_number,
        class_name=class_name,
        subject=subject,
        book=book,
    )

    if lesson is None:
        raise ValueError(
            f"Lesson {lesson_number} could not be found."
        )

    lesson_content = str(
        lesson.get("content") or ""
    ).strip()

    if not lesson_content:
        raise ValueError(
            f"Lesson {lesson_number} contains no text."
        )

    # --------------------------------------------------------
    # Protect LLM context.
    # --------------------------------------------------------

    if len(lesson_content) > MAX_LESSON_CHARS:

        lesson_content = lesson_content[
            :MAX_LESSON_CHARS
        ]

        print(
            "WARNING: Lesson content truncated to "
            f"{MAX_LESSON_CHARS} characters."
        )

    # --------------------------------------------------------
    # Generate + validate + retry.
    # --------------------------------------------------------

    last_error = None
    data = None

    for attempt in range(
        1,
        MAX_GENERATION_ATTEMPTS + 1,
    ):

        print(
            "Oral question bank generation "
            f"attempt {attempt}/"
            f"{MAX_GENERATION_ATTEMPTS}"
        )

        prompt = _build_prompt(
            lesson_content=lesson_content,
            lesson_number=lesson_number,
            lesson_title=lesson["title"],
            language=language,
            question_count=question_count,
            previous_error=last_error,
        )

        try:

            response = question_bank_llm.invoke(
                prompt
            )

            raw_content = getattr(
                response,
                "content",
                "",
            )

            if isinstance(
                raw_content,
                list,
            ):

                parts = []

                for item in raw_content:

                    if isinstance(
                        item,
                        str,
                    ):
                        parts.append(
                            item
                        )

                    elif isinstance(
                        item,
                        dict,
                    ):

                        text = item.get(
                            "text"
                        )

                        if text:
                            parts.append(
                                str(text)
                            )

                raw_content = "".join(
                    parts
                )

            raw_content = str(
                raw_content or ""
            ).strip()

            if not raw_content:
                raise ValueError(
                    "LLM returned an empty response."
                )

            generated = _extract_json(
                raw_content
            )

            data = _validate_question_bank(
                data=generated,
                lesson_content=lesson_content,
                expected_count=question_count,
            )

            # Successful generation.
            break

        except Exception as exc:

            last_error = str(
                exc
            )

            print(
                "Oral question bank validation failed:"
            )

            print(
                last_error
            )

            data = None

    # --------------------------------------------------------
    # All attempts failed.
    # --------------------------------------------------------

    if data is None:

        raise ValueError(
            "Could not generate a fully "
            "textbook-grounded oral question bank "
            f"after {MAX_GENERATION_ATTEMPTS} attempts. "
            f"Last error: {last_error}"
        )

    # --------------------------------------------------------
    # Add metadata.
    # --------------------------------------------------------

    data["lesson_number"] = (
        lesson_number
    )

    data["lesson_title"] = (
        lesson["title"]
    )

    data["language"] = (
        language
    )

    data["source"] = {
        "class": class_name,
        "subject": subject,
        "book": book,
        "pdf_start_page": lesson[
            "start_pdf_page"
        ],
        "pdf_end_page": lesson[
            "end_pdf_page"
        ],
        "lesson_page_count": lesson[
            "page_count"
        ],
    }

    data["total_questions"] = (
        len(
            data.get(
                "questions",
                [],
            )
        )
    )

    # --------------------------------------------------------
    # Evidence is internal.
    # --------------------------------------------------------

    data = _remove_evidence(
        data
    )

    return data


# ============================================================
# RANDOM QUESTION SELECTION
# ============================================================

def select_oral_questions(
    question_bank: dict,
    count: int = 10,
    difficulty: str = "balanced",
    seed: int | None = None,
) -> list[dict]:
    """
    Select random questions from a generated question bank.

    difficulty:
        balanced
        easy
        medium
        hard

    A seed can be supplied so a particular Roll No. can receive
    a repeatable test.
    """

    try:
        count = int(count)
    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Question count must be an integer."
        )

    if count <= 0:
        raise ValueError(
            "Question count must be greater than zero."
        )

    questions = question_bank.get(
        "questions",
        [],
    )

    if not isinstance(
        questions,
        list,
    ):
        raise ValueError(
            "Invalid question bank."
        )

    if len(questions) < count:
        raise ValueError(
            f"Question bank contains only "
            f"{len(questions)} questions, "
            f"but {count} were requested."
        )

    difficulty = str(
        difficulty or "balanced"
    ).lower().strip()

    rng = random.Random(
        seed
    )

    # --------------------------------------------------------
    # Specific difficulty.
    # --------------------------------------------------------

    if difficulty in {
        "easy",
        "medium",
        "hard",
    }:

        filtered = [
            question
            for question in questions
            if str(
                question.get("difficulty", "")
            ).lower()
            == difficulty
        ]

        if len(filtered) < count:
            raise ValueError(
                f"Not enough {difficulty} questions."
            )

        selected = rng.sample(
            filtered,
            count,
        )

        return selected

    # --------------------------------------------------------
    # Balanced difficulty.
    #
    # Approximate:
    # 40% easy
    # 40% medium
    # 20% hard
    # --------------------------------------------------------

    easy = [
        q
        for q in questions
        if q.get("difficulty") == "easy"
    ]

    medium = [
        q
        for q in questions
        if q.get("difficulty") == "medium"
    ]

    hard = [
        q
        for q in questions
        if q.get("difficulty") == "hard"
    ]

    rng.shuffle(
        easy
    )

    rng.shuffle(
        medium
    )

    rng.shuffle(
        hard
    )

    easy_count = round(
        count * 0.40
    )

    medium_count = round(
        count * 0.40
    )

    hard_count = (
        count
        - easy_count
        - medium_count
    )

    selected = (
        easy[:easy_count]
        + medium[:medium_count]
        + hard[:hard_count]
    )

    # --------------------------------------------------------
    # If a difficulty group does not contain enough questions,
    # fill remaining positions from the complete bank.
    # --------------------------------------------------------

    if len(selected) < count:

        selected_ids = {
            id(q)
            for q in selected
        }

        remaining = [
            q
            for q in questions
            if id(q)
            not in selected_ids
        ]

        rng.shuffle(
            remaining
        )

        selected.extend(
            remaining[
                :count - len(selected)
            ]
        )

    rng.shuffle(
        selected
    )

    return selected[:count]


# ============================================================
# ROLL NUMBER BASED TEST
# ============================================================

def generate_student_oral_test(
    question_bank: dict,
    roll_number: str | int,
    question_count: int = 10,
    difficulty: str = "balanced",
) -> dict:
    """
    Generate a student's oral test.

    The roll number is converted into a deterministic seed.

    Therefore:

        Roll 1 → repeatable set
        Roll 2 → different set
        Roll 3 → different set

    The same roll number can reproduce the same test if the
    question bank has not changed.
    """

    roll_text = str(
        roll_number
    ).strip()

    if not roll_text:
        raise ValueError(
            "Roll number is required."
        )

    # Stable deterministic seed.
    seed_text = (
        f"{question_bank.get('lesson_number', '')}:"
        f"{roll_text}"
    )

    seed = sum(
        (
            index + 1
        )
        * ord(character)
        for index, character
        in enumerate(seed_text)
    )

    selected = select_oral_questions(
        question_bank=question_bank,
        count=question_count,
        difficulty=difficulty,
        seed=seed,
    )

    return {
        "roll_number": roll_text,
        "lesson_number": question_bank.get(
            "lesson_number"
        ),
        "lesson_title": question_bank.get(
            "lesson_title"
        ),
        "questions": selected,
        "total_questions": len(
            selected
        ),
    }
