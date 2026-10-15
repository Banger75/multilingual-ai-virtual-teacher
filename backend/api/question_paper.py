"""
Question Paper API
==================

FastAPI endpoint for generating a question paper
from a selected textbook lesson.

Endpoint:

POST /api/question-paper
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.ai.question_generator import generate_question_paper


router = APIRouter(
    prefix="/api/question-paper",
    tags=["Question Paper"],
)


# ============================================================
# REQUEST SCHEMA
# ============================================================

class QuestionPaperRequest(BaseModel):
    """
    Request sent by the frontend.
    """

    lesson_number: int = Field(
        ...,
        ge=1,
        description="Lesson number",
    )

    class_name: str | None = None

    subject: str | None = None

    book: str | None = None

    language: str = "auto"

    mcq_count: int = Field(
        0,
        ge=0,
        le=50,
    )

    fill_blank_count: int = Field(
        0,
        ge=0,
        le=50,
    )

    true_false_count: int = Field(
        0,
        ge=0,
        le=50,
    )

    short_answer_count: int = Field(
        0,
        ge=0,
        le=50,
    )


# ============================================================
# RESPONSE
# ============================================================

@router.post("")
def create_question_paper(
    request: QuestionPaperRequest,
):
    """
    Generate a question paper from one textbook lesson.
    """

    total_questions = (
        request.mcq_count
        + request.fill_blank_count
        + request.true_false_count
        + request.short_answer_count
    )

    if total_questions <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one question is required. "
                "Please select a question count."
            ),
        )

    try:

        paper = generate_question_paper(
            lesson_number=request.lesson_number,
            class_name=request.class_name,
            subject=request.subject,
            book=request.book,
            language=request.language,
            mcq_count=request.mcq_count,
            fill_blank_count=request.fill_blank_count,
            true_false_count=request.true_false_count,
            short_answer_count=request.short_answer_count,
        )

        return paper

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        print(
            "QUESTION PAPER API ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to generate the question paper."
            ),
        )