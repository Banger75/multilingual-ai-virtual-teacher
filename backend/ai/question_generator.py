"""
Question Paper Generator for the Subject Specific Virtual Teacher.

Features:
    - Generates MCQs
    - Generates fill-in-the-blanks
    - Generates True/False
    - Generates short-answer questions
    - Uses only the selected lesson
    - Requires evidence for every generated question
    - Validates evidence against the actual lesson
    - Automatically retries invalid generation
    - Removes internal evidence before returning the final paper

The normal teacher Q&A system is not affected.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI

from backend.config import settings
from backend.ai.lesson_resolver import get_lesson_content


# ============================================================
# QUESTION GENERATOR LLM
# ============================================================

question_llm = ChatOpenAI(
    model=settings.llm_model,
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    temperature=0.25,
    max_tokens=5000,
    extra_body={
        "Chat_templete_kwargs": {
            "enable_thinking": False
        }
    },
)


# ============================================================
# CONFIGURATION
# ============================================================

MAX_LESSON_CHARS = 25000

# Number of attempts when validation fails.
MAX_GENERATION_ATTEMPTS = 3


# ============================================================
# HELPERS
# ============================================================

def _clean_json_text(text: str) -> str:
    """
    Remove common markdown wrappers around JSON.
    """

    if not text:
        return ""

    text = text.strip()

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
    Extract a JSON object from the model response.
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
        "The question generator returned invalid JSON."
    )


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:

    try:

        number = int(value)

        return max(
            0,
            number,
        )

    except (
        TypeError,
        ValueError,
    ):

        return default


def _normalize_question_text(
    text: Any,
) -> str:

    value = str(
        text or ""
    ).strip().lower()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    value = re.sub(
        r"[^\w\s]",
        "",
        value,
    )

    return value


def _validate_non_empty_text(
    value: Any,
    field_name: str,
) -> str:

    text = str(
        value or ""
    ).strip()

    if not text:

        raise ValueError(
            f"{field_name} cannot be empty."
        )

    return text


def _normalize_for_evidence(
    text: str,
) -> str:
    """
    Normalize text so evidence can be compared with
    textbook text despite minor whitespace/punctuation
    differences.
    """

    text = str(
        text or ""
    ).lower()

    text = text.replace(
        "\u2018",
        "'",
    )

    text = text.replace(
        "\u2019",
        "'",
    )

    text = text.replace(
        "\u201c",
        '"',
    )

    text = text.replace(
        "\u201d",
        '"',
    )

    text = text.replace(
        "\u2013",
        "-",
    )

    text = text.replace(
        "\u2014",
        "-",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = re.sub(
        r"[^\w\s']",
        "",
        text,
    )

    return text.strip()


def _evidence_exists(
    evidence: str,
    lesson_content: str,
) -> bool:
    """
    Check whether the supplied evidence is actually present
    in the lesson.

    We use normalized substring matching first.

    A shorter normalized comparison is also allowed because
    PDF extraction may contain line breaks or unusual spacing.
    """

    evidence_normalized = _normalize_for_evidence(
        evidence
    )

    lesson_normalized = _normalize_for_evidence(
        lesson_content
    )

    if not evidence_normalized:
        return False

    if not lesson_normalized:
        return False

    # --------------------------------------------------------
    # Strongest check: complete evidence exists.
    # --------------------------------------------------------

    if evidence_normalized in lesson_normalized:
        return True

    # --------------------------------------------------------
    # If the model returned a long evidence sentence,
    # compare its meaningful chunks.
    # --------------------------------------------------------

    sentences = re.split(
        r"[.!?]+",
        evidence_normalized,
    )

    meaningful_sentences = [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) >= 20
    ]

    if not meaningful_sentences:
        return False

    matched = sum(
        1
        for sentence in meaningful_sentences
        if sentence in lesson_normalized
    )

    return matched == len(
        meaningful_sentences
    )


# ============================================================
# BUILD QUESTION GENERATION PROMPT
# ============================================================

def _build_prompt(
    lesson_content: str,
    lesson_number: int,
    lesson_title: str,
    language: str,
    mcq_count: int,
    fill_blank_count: int,
    true_false_count: int,
    short_answer_count: int,
    previous_error: str | None = None,
) -> str:

    answer_language = (
        language
        if language
        and language.lower() not in {
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

The previous question paper failed validation.

Reason:

{previous_error}

You MUST correct this problem.

Do not repeat the invalid question.

Generate a new complete question paper.

============================================================
"""

    return f"""
/no_think

You are an experienced school teacher creating a question paper
for a government-school classroom.

Your ONLY source of knowledge is the supplied textbook lesson.

{retry_instruction}

============================================================
LESSON INFORMATION
============================================================

Lesson number: {lesson_number}

Lesson title:
{lesson_title}

Required language:
{answer_language}

============================================================
QUESTION COUNTS
============================================================

MCQ: {mcq_count}

Fill in the blanks: {fill_blank_count}

True/False: {true_false_count}

Short answer: {short_answer_count}

============================================================
STRICT TEXTBOOK RULE
============================================================

EVERY question and EVERY answer must be supported by the
supplied textbook lesson.

Do NOT use:

- general knowledge
- internet knowledge
- model memory
- facts from another lesson
- facts from another textbook
- assumptions
- invented facts
- unsupported conclusions
- invented moral lessons
- invented messages
- personal opinions

If the lesson does not provide the information,
DO NOT create a question about it.

============================================================
IMPORTANT: EVIDENCE
============================================================

For EVERY question, provide an "evidence" field.

The evidence must be an exact sentence or exact factual
phrase copied from the supplied lesson content.

The evidence must directly support the answer.

Do NOT write new evidence.

Do NOT summarize the evidence.

Do NOT explain the evidence.

COPY the supporting wording from the textbook content.

The Python application will verify that the evidence exists
inside the lesson.

============================================================
QUESTION RULES
============================================================

1. Questions must be suitable for the student's class.

2. Questions must be based only on this lesson.

3. Do not copy textbook exercise questions word-for-word.

4. You may rephrase textbook facts into new questions.

5. Do not create duplicate questions.

6. Do not use information outside the lesson.

7. Every question must have exactly one clear answer.

8. DO NOT create questions asking for:
   - the moral of the story
   - the message of the story
   - the lesson learned
   - the main lesson
   - the moral lesson
   - the author's message
   - what students should learn
   - what the story teaches

UNLESS the textbook lesson explicitly states the answer.

9. Never infer a moral or message from events in the story.

10. Never convert an implied idea into a textbook fact.

11. Questions must be about information explicitly present
    in the supplied lesson.

12. Prefer questions about:
    - characters
    - names
    - dates
    - events
    - actions
    - objects
    - places
    - numbers
    - vocabulary
    - directly stated information.
============================================================
MCQ RULES
============================================================

Each MCQ must contain:

A
B
C
D

Exactly four options.

Only one option is correct.

The correct option must be supported by the evidence.

Avoid simple Yes/No questions converted into MCQs.

============================================================
FILL-IN-THE-BLANK RULES
============================================================

Each question must contain a blank.

The answer must be directly present in the lesson.

The evidence must contain the answer or directly support it.

============================================================
TRUE/FALSE RULES
============================================================

The evidence must explicitly state or clearly show that
the statement is true.

For FALSE statements:

The evidence must explicitly provide the CORRECT FACT that
contradicts the statement.

Example:

Statement:
"Birbal drew a circle on the floor."

Answer:
false

Evidence:
"He took the piece of charcoal and drew another line,
next to the line Akbar had drawn."

This is acceptable because the textbook describes what
Birbal actually drew.

Do NOT create false statements using unrelated information.

Do NOT create false statements merely because the textbook
does not mention something.

Every FALSE statement must have contradictory textbook evidence.

============================================================
SHORT-ANSWER RULES
============================================================

Short-answer questions should normally require
1-3 sentences.

The answer must be directly supported by the lesson.

Do not ask for:

- personal opinions
- morals
- messages
- conclusions
- lessons learned
- assumptions

unless explicitly stated in the textbook.

============================================================
REQUIRED JSON
============================================================

{{
  "lesson_number": {lesson_number},
  "lesson_title": "{lesson_title}",
  "language": "{answer_language}",

  "mcqs": [
    {{
      "question": "Question",
      "options": {{
        "A": "Option A",
        "B": "Option B",
        "C": "Option C",
        "D": "Option D"
      }},
      "answer": "A",
      "evidence": "Exact supporting text from lesson"
    }}
  ],

  "fill_in_the_blanks": [
    {{
      "question": "Question with ________",
      "answer": "Answer",
      "evidence": "Exact supporting text from lesson"
    }}
  ],

  "true_false": [
    {{
      "question": "Statement",
      "answer": true,
      "evidence": "Exact supporting text from lesson"
    }}
  ],

  "short_answers": [
    {{
      "question": "Question",
      "answer": "Short answer",
      "evidence": "Exact supporting text from lesson"
    }}
  ]
}}

============================================================
TEXTBOOK LESSON
============================================================

{lesson_content}

============================================================
END TEXTBOOK LESSON
============================================================

Generate EXACTLY the requested number of questions.

Return ONLY valid JSON.
"""
# ============================================================
# ANSWER / EVIDENCE VALIDATION
# ============================================================

def _tokenize_evidence(text: str) -> list[str]:
    """
    Convert text into normalized word tokens.

    This removes punctuation and performs a small amount of
    normalization so that:

        touch
        touching
        touched

    can be compared reasonably.

    This is intentionally lightweight. We do not want an
    aggressive NLP system here because textbook grounding
    should remain strict.
    """

    text = _normalize_for_evidence(text)

    # Replace punctuation with spaces.
    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    tokens = text.split()

    normalized_tokens = []

    for token in tokens:

        # ----------------------------------------------------
        # Basic English suffix normalization.
        # ----------------------------------------------------

        if len(token) > 5 and token.endswith("ing"):
            token = token[:-3]

        elif len(token) > 4 and token.endswith("ed"):
            token = token[:-2]

        elif len(token) > 4 and token.endswith("es"):
            token = token[:-2]

        elif len(token) > 3 and token.endswith("s"):
            token = token[:-1]

        normalized_tokens.append(token)

    return normalized_tokens


def _answer_is_supported_by_evidence(
    question: str,
    answer: str,
    evidence: str,
) -> bool:
    """
    Check whether the generated answer is supported by the
    supplied textbook evidence.

    The LLM is allowed to rephrase textbook information.

    Examples:

        Answer:
            Make the line shorter without touching it.

        Evidence:
            You have to make this line shorter but you should
            not touch it.

    This should be accepted because the important factual
    concepts are present in the evidence.

    The validator still rejects answers that introduce
    unrelated facts.
    """

    answer_text = _normalize_for_evidence(
        answer
    )

    evidence_text = _normalize_for_evidence(
        evidence
    )

    if not answer_text:
        return False

    if not evidence_text:
        return False

    # ========================================================
    # 1. Direct containment
    # ========================================================

    if answer_text in evidence_text:
        return True

    # ========================================================
    # 2. Numeric answers
    # ========================================================

    if re.fullmatch(
        r"\d+",
        answer_text,
    ):

        return answer_text in evidence_text

    # ========================================================
    # 3. Token-based comparison
    # ========================================================

    answer_tokens = _tokenize_evidence(
        answer_text
    )

    evidence_tokens = _tokenize_evidence(
        evidence_text
    )

    if not answer_tokens or not evidence_tokens:
        return False

    evidence_token_set = set(
        evidence_tokens
    )

    # --------------------------------------------------------
    # Ignore common grammatical words.
    #
    # These words do not normally represent textbook facts.
    # --------------------------------------------------------

    stop_words = {
        "a",
        "an",
        "the",
        "is",
        "was",
        "were",
        "are",
        "am",
        "be",
        "been",
        "being",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "from",
        "with",
        "by",
        "and",
        "or",
        "but",
        "he",
        "she",
        "it",
        "they",
        "them",
        "his",
        "her",
        "their",
        "this",
        "that",
        "these",
        "those",
        "you",
        "we",
        "i",
        "who",
        "what",
        "how",
        "when",
        "where",
        "why",
        "did",
        "do",
        "does",
        "has",
        "have",
        "had",
        "will",
        "would",
        "could",
        "should",
        "can",
        "may",
        "must",
        "as",
        "into",
        "then",
        "than",
    }

    answer_content_tokens = [
        token
        for token in answer_tokens
        if token not in stop_words
    ]

    evidence_content_tokens = [
        token
        for token in evidence_tokens
        if token not in stop_words
    ]

    if not answer_content_tokens:
        return False

    evidence_content_set = set(
        evidence_content_tokens
    )

    # ========================================================
    # 4. Exact content-word matching
    # ========================================================

    matched_tokens = sum(
        1
        for token in answer_content_tokens
        if token in evidence_content_set
    )

    content_count = len(
        answer_content_tokens
    )

    match_ratio = (
        matched_tokens / content_count
    )

    # --------------------------------------------------------
    # Strong match.
    # --------------------------------------------------------

    if match_ratio >= 0.75:
        return True

    # ========================================================
    # 5. Handle common textbook paraphrasing
    # ========================================================
    #
    # Example:
    #
    # Answer:
    #   without touching
    #
    # Evidence:
    #   should not touch
    #
    # "without" and "not" express the same negative idea.
    #
    # We therefore check whether the main action/content
    # words are present.
    # ========================================================

    # Remove common negation/grammar words when calculating
    # the factual core.
    semantic_stop_words = stop_words | {
        "without",
        "not",
        "no",
        "never",
        "very",
        "more",
        "some",
        "any",
        "all",
    }

    answer_core = [
        token
        for token in answer_tokens
        if token not in semantic_stop_words
    ]

    evidence_core = [
        token
        for token in evidence_tokens
        if token not in semantic_stop_words
    ]

    if answer_core:

        evidence_core_set = set(
            evidence_core
        )

        core_matches = sum(
            1
            for token in answer_core
            if token in evidence_core_set
        )

        core_ratio = (
            core_matches / len(answer_core)
        )

        # Very strong factual overlap.
        if (
            len(answer_core) >= 2
            and core_ratio >= 0.80
        ):
            return True

    # ========================================================
    # 6. Special handling for negative/paraphrased actions
    # ========================================================
    #
    # "without touching it"
    #
    # can correspond to:
    #
    # "should not touch it"
    #
    # We require the important action word to occur.
    # ========================================================

    negative_words = {
        "without",
        "not",
        "never",
        "no",
    }

    answer_has_negative = any(
        word in answer_tokens
        for word in negative_words
    )

    evidence_has_negative = any(
        word in evidence_tokens
        for word in negative_words
    )

    if (
        answer_has_negative
        and evidence_has_negative
    ):

        important_answer_tokens = [
            token
            for token in answer_content_tokens
            if token not in negative_words
        ]

        if important_answer_tokens:

            important_matches = sum(
                1
                for token in important_answer_tokens
                if token in evidence_content_set
            )

            important_ratio = (
                important_matches
                / len(important_answer_tokens)
            )

            if important_ratio >= 0.75:
                return True

    # ========================================================
    # 7. Otherwise reject
    # ========================================================

    return False
# ============================================================
# VALIDATE GENERATED PAPER
# ============================================================

def _validate_question_paper(
    data: dict,
    mcq_count: int,
    fill_blank_count: int,
    true_false_count: int,
    short_answer_count: int,
    lesson_content: str = "",
) -> dict:

    if not isinstance(data, dict):

        raise ValueError(
            "Question paper response is not an object."
        )

    mcqs = data.get(
        "mcqs",
        [],
    )

    fill_blanks = data.get(
        "fill_in_the_blanks",
        [],
    )

    true_false = data.get(
        "true_false",
        [],
    )

    short_answers = data.get(
        "short_answers",
        [],
    )

    if not isinstance(mcqs, list):
        mcqs = []

    if not isinstance(fill_blanks, list):
        fill_blanks = []

    if not isinstance(true_false, list):
        true_false = []

    if not isinstance(short_answers, list):
        short_answers = []

    # ========================================================
    # COUNT VALIDATION
    # ========================================================

    if len(mcqs) != mcq_count:

        raise ValueError(
            f"Expected {mcq_count} MCQs, "
            f"but model generated {len(mcqs)}."
        )

    if len(fill_blanks) != fill_blank_count:

        raise ValueError(
            f"Expected {fill_blank_count} fill-in-the-blanks, "
            f"but model generated {len(fill_blanks)}."
        )

    if len(true_false) != true_false_count:

        raise ValueError(
            f"Expected {true_false_count} true/false questions, "
            f"but model generated {len(true_false)}."
        )

    if len(short_answers) != short_answer_count:

        raise ValueError(
            f"Expected {short_answer_count} short-answer questions, "
            f"but model generated {len(short_answers)}."
        )

    # ========================================================
    # DUPLICATE DETECTION
    # ========================================================

    seen_questions = set()

    def register_question(
        question: str,
        label: str,
    ):

        normalized = _normalize_question_text(
            question
        )

        if not normalized:

            raise ValueError(
                f"{label} has an empty question."
            )

        if normalized in seen_questions:

            raise ValueError(
                f"Duplicate question detected: {question}"
            )

        seen_questions.add(
            normalized
        )

    # ========================================================
    # EVIDENCE VALIDATION
    # ========================================================

    def validate_evidence(
        item: dict,
        label: str,
    ):

        evidence = _validate_non_empty_text(
            item.get("evidence"),
            f"{label} evidence",
        )

    # --------------------------------------------------------
    # 1. Evidence must actually exist in the textbook.
    # --------------------------------------------------------

        if not _evidence_exists(
            evidence,
            lesson_content,
        ):

            raise ValueError(
                f"{label} contains evidence that "
                f"cannot be found in the lesson: "
                f"{evidence}"
            )

        # --------------------------------------------------------
        # 2. Answer must be supported by the evidence.
        # --------------------------------------------------------

        answer = item.get(
            "answer"
        )

        # MCQ answer is a letter. For MCQs we validate the
        # selected option instead.
        if label.startswith("MCQ"):

            options = item.get(
                "options",
                {},
            )

            answer_key = str(
                answer or ""
            ).strip().upper()

            selected_answer = (
                options.get(answer_key)
                if isinstance(options, dict)
                else ""
            )

            if not _answer_is_supported_by_evidence(
                item.get("question", ""),
                selected_answer,
                evidence,
            ):

                raise ValueError(
                    f"{label} answer is not supported "
                    f"by its textbook evidence.\n"
                    f"Answer: {selected_answer}\n"
                    f"Evidence: {evidence}"
                )

    # --------------------------------------------------------
    # Fill blanks / short answers.
    # --------------------------------------------------------

        elif label.startswith(
            "Fill-in-the-blank"
        ) or label.startswith(
            "Short answer"
        ):

            if not _answer_is_supported_by_evidence(
                item.get("question", ""),
                str(answer or ""),
                evidence,
            ):

                raise ValueError(
                    f"{label} answer is not supported "
                    f"by its textbook evidence.\n"
                    f"Answer: {answer}\n"
                    f"Evidence: {evidence}"
                )

    # --------------------------------------------------------
    # True / False
    #
    # The evidence must support the actual truth value.
    # The LLM is required to provide evidence that directly
    # establishes the statement.
    #
    # For now, ensure the statement's important words occur
    # in the evidence.
    # --------------------------------------------------------

        elif label.startswith(
            "True/False"
        ):

            question_text = (
                item.get("question", "")
            )

            if not _answer_is_supported_by_evidence(
                question_text,
                question_text,
                evidence,
            ):

                raise ValueError(
                    f"{label} statement is not "
                    f"supported by its textbook evidence.\n"
                    f"Statement: {question_text}\n"
                    f"Evidence: {evidence}"
                )

        item["evidence"] = evidence

    # ========================================================
    # MCQ VALIDATION
    # ========================================================

    for index, item in enumerate(
        mcqs,
        1,
    ):

        if not isinstance(item, dict):

            raise ValueError(
                f"MCQ {index} is invalid."
            )

        question = _validate_non_empty_text(
            item.get("question"),
            f"MCQ {index} question",
        )

        options = item.get(
            "options"
        )

        answer = str(
            item.get("answer") or ""
        ).strip().upper()

        register_question(
            question,
            f"MCQ {index}",
        )

        if not isinstance(options, dict):

            raise ValueError(
                f"MCQ {index} has no options."
            )

        required_options = {
            "A",
            "B",
            "C",
            "D",
        }

        if set(options.keys()) != required_options:

            raise ValueError(
                f"MCQ {index} must contain "
                "exactly A, B, C and D."
            )

        if answer not in required_options:

            raise ValueError(
                f"MCQ {index} has invalid answer: {answer}"
            )

        normalized_options = {}

        for key in (
            "A",
            "B",
            "C",
            "D",
        ):

            normalized_options[key] = (
                _validate_non_empty_text(
                    options[key],
                    f"MCQ {index} option {key}",
                )
            )

        item["question"] = question
        item["options"] = normalized_options
        item["answer"] = answer

        validate_evidence(
            item,
            f"MCQ {index}",
        )

    # ========================================================
    # FILL-IN-THE-BLANK VALIDATION
    # ========================================================

    for index, item in enumerate(
        fill_blanks,
        1,
    ):

        if not isinstance(item, dict):

            raise ValueError(
                f"Fill-in-the-blank {index} is invalid."
            )

        question = _validate_non_empty_text(
            item.get("question"),
            f"Fill-in-the-blank {index} question",
        )

        answer = _validate_non_empty_text(
            item.get("answer"),
            f"Fill-in-the-blank {index} answer",
        )

        register_question(
            question,
            f"Fill-in-the-blank {index}",
        )

        if not re.search(
            r"_{2,}|…+|\.{3,}",
            question,
        ):

            raise ValueError(
                f"Fill-in-the-blank {index} "
                "does not contain a blank."
            )

        item["question"] = question
        item["answer"] = answer

        validate_evidence(
            item,
            f"Fill-in-the-blank {index}",
        )

    # ========================================================
    # TRUE/FALSE VALIDATION
    # ========================================================

    for index, item in enumerate(
        true_false,
        1,
    ):

        if not isinstance(item, dict):

            raise ValueError(
                f"True/False {index} is invalid."
            )

        question = _validate_non_empty_text(
            item.get("question"),
            f"True/False {index} question",
        )

        register_question(
            question,
            f"True/False {index}",
        )

        answer = item.get(
            "answer"
        )

        if isinstance(answer, str):

            answer_lower = (
                answer.strip().lower()
            )

            if answer_lower == "true":

                answer = True

            elif answer_lower == "false":

                answer = False

            else:

                raise ValueError(
                    f"True/False {index} "
                    "has invalid answer."
                )

        if not isinstance(answer, bool):

            raise ValueError(
                f"True/False {index} answer "
                "must be true or false."
            )

        item["question"] = question
        item["answer"] = answer

        validate_evidence(
            item,
            f"True/False {index}",
        )

    # ========================================================
    # SHORT-ANSWER VALIDATION
    # ========================================================

    for index, item in enumerate(
        short_answers,
        1,
    ):

        if not isinstance(item, dict):

            raise ValueError(
                f"Short answer {index} is invalid."
            )

        question = _validate_non_empty_text(
            item.get("question"),
            f"Short answer {index} question",
        )

        answer = _validate_non_empty_text(
            item.get("answer"),
            f"Short answer {index} answer",
        )

        register_question(
            question,
            f"Short answer {index}",
        )

        item["question"] = question
        item["answer"] = answer

        validate_evidence(
            item,
            f"Short answer {index}",
        )

    return data


# ============================================================
# REMOVE INTERNAL EVIDENCE
# ============================================================

def _remove_evidence(
    data: dict,
) -> dict:
    """
    Evidence is an internal validation field.

    It should NOT be sent to the student/frontend.
    """

    sections = (
        "mcqs",
        "fill_in_the_blanks",
        "true_false",
        "short_answers",
    )

    for section in sections:

        items = data.get(
            section,
            [],
        )

        if not isinstance(items, list):
            continue

        for item in items:

            if isinstance(item, dict):

                item.pop(
                    "evidence",
                    None,
                )

    return data


# ============================================================
# GENERATE QUESTION PAPER
# ============================================================

def generate_question_paper(
    lesson_number: int,
    class_name=None,
    subject=None,
    book=None,
    language="auto",
    mcq_count: int = 0,
    fill_blank_count: int = 0,
    true_false_count: int = 0,
    short_answer_count: int = 0,
) -> dict:

    lesson_number = _safe_int(
        lesson_number
    )

    mcq_count = _safe_int(
        mcq_count
    )

    fill_blank_count = _safe_int(
        fill_blank_count
    )

    true_false_count = _safe_int(
        true_false_count
    )

    short_answer_count = _safe_int(
        short_answer_count
    )

    total_questions = (
        mcq_count
        + fill_blank_count
        + true_false_count
        + short_answer_count
    )

    if lesson_number <= 0:

        raise ValueError(
            "Lesson number must be greater than zero."
        )

    if total_questions <= 0:

        raise ValueError(
            "At least one question is required."
        )

    # ========================================================
    # RETRIEVE LESSON
    # ========================================================

    lesson = get_lesson_content(
        lesson_number=lesson_number,
        class_name=class_name,
        subject=subject,
        book=book,
    )

    if lesson is None:

        raise ValueError(
            f"Lesson {lesson_number} could not be found "
            f"in the selected textbook."
        )

    lesson_content = (
        lesson.get("content") or ""
    ).strip()

    if not lesson_content:

        raise ValueError(
            f"Lesson {lesson_number} contains no text."
        )

    if len(lesson_content) > MAX_LESSON_CHARS:

        lesson_content = (
            lesson_content[:MAX_LESSON_CHARS]
        )

        print(
            "WARNING: Lesson content was truncated "
            f"to {MAX_LESSON_CHARS} characters."
        )

    # ========================================================
    # GENERATION + AUTOMATIC RETRY
    # ========================================================

    data = None
    last_error = None

    for attempt in range(
        1,
        MAX_GENERATION_ATTEMPTS + 1,
    ):

        print(
            f"Question paper generation attempt "
            f"{attempt}/{MAX_GENERATION_ATTEMPTS}"
        )

        prompt = _build_prompt(
            lesson_content=lesson_content,
            lesson_number=lesson_number,
            lesson_title=lesson["title"],
            language=language,
            mcq_count=mcq_count,
            fill_blank_count=fill_blank_count,
            true_false_count=true_false_count,
            short_answer_count=short_answer_count,
            previous_error=last_error,
        )

        try:

            response = question_llm.invoke(
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
                    "The question generator "
                    "returned an empty response."
                )

            generated_data = _extract_json(
                raw_content
            )

            generated_data = (
                _validate_question_paper(
                    data=generated_data,
                    mcq_count=mcq_count,
                    fill_blank_count=fill_blank_count,
                    true_false_count=true_false_count,
                    short_answer_count=short_answer_count,
                    lesson_content=lesson_content,
                )
            )

            data = generated_data

            print(
                "Question paper validation PASSED."
            )

            break

        except Exception as exc:

            last_error = str(
                exc
            )

            print(
                "Question paper validation FAILED:"
            )

            print(
                last_error
            )

            data = None

    # ========================================================
    # ALL ATTEMPTS FAILED
    # ========================================================

    if data is None:

        raise ValueError(
            "Could not generate a fully "
            "textbook-grounded question paper "
            f"after {MAX_GENERATION_ATTEMPTS} attempts. "
            f"Last error: {last_error}"
        )

    # ========================================================
    # APPLICATION METADATA
    # ========================================================

    data["lesson_number"] = (
        lesson_number
    )

    data["lesson_title"] = (
        lesson["title"]
    )

    data["language"] = (
        language
        if language
        and language.lower() not in {
            "auto",
            "same",
        }
        else lesson.get(
            "language",
            language,
        )
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
        total_questions
    )

    # ========================================================
    # REMOVE INTERNAL EVIDENCE
    # ========================================================

    data = _remove_evidence(
        data
    )

    return data


# ============================================================
# SIMPLE CONVENIENCE FUNCTION
# ============================================================

def generate_lesson_test(
    lesson_number: int,
    class_name=None,
    subject=None,
    book=None,
    language="auto",
    count_each: int = 5,
) -> dict:

    count_each = _safe_int(
        count_each
    )

    return generate_question_paper(
        lesson_number=lesson_number,
        class_name=class_name,
        subject=subject,
        book=book,
        language=language,
        mcq_count=count_each,
        fill_blank_count=count_each,
        true_false_count=count_each,
        short_answer_count=count_each,
    )