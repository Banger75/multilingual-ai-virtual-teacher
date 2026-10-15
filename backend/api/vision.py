from __future__ import annotations

import base64
import logging
import shutil
import traceback
import uuid
from pathlib import Path

import requests
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.config import settings
from backend.speech.tts import text_to_speech
from backend.vision.analyzer import analyze_page_image, explain_book_page


router = APIRouter(prefix="/api/vision", tags=["Vision"])
logger = logging.getLogger("uvicorn.error")


class VisionRequest(BaseModel):
    question: str = Field(min_length=1)
    class_name: str | None = None
    subject: str | None = None
    book: str = Field(min_length=1)
    language: str = "auto"


# ============================================================
# EXISTING TEXTBOOK PAGE VISION
# ============================================================

@router.post("/explain")
def explain(request: VisionRequest):
    try:
        logger.info(
            "VISION REQUEST: class=%r subject=%r book=%r language=%r question=%r",
            request.class_name,
            request.subject,
            request.book,
            request.language,
            request.question,
        )

        return explain_book_page(
            question=request.question,
            book=request.book,
            language=request.language,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.error(
            "VISION FAILED:\n%s",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================
# UPLOADED PAGE / IMAGE
# ============================================================

ALLOWED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


def _create_answer_audio(
    *,
    answer: str,
    language: str,
    response_mode: str,
) -> str | None:
    """Create optional speech for an uploaded-page explanation.

    Uploaded pages use a normal JSON response rather than the chat stream,
    but they should honor the same Spoken and Both response modes as chat.
    A speech failure must not prevent the student from receiving the answer.
    """
    if response_mode.strip().lower() not in {"spoken", "both"}:
        return None

    try:
        filename = text_to_speech(answer, language=language)
        return f"/audio/{filename}"
    except Exception as exc:
        logger.warning("UPLOADED PAGE TTS FAILED: %s", exc)
        return None


def is_explicit_visual_question(question: str) -> bool:
    """
    Decide whether the student explicitly wants a visual explanation.

    IMPORTANT:
    Words such as "page" do NOT trigger vision.

    Examples:

        Explain page 13
            -> TEXT

        Explain this page
            -> TEXT

        What is written on this page?
            -> TEXT

        Explain the picture on page 13
            -> VISION

        What is happening in this picture?
            -> VISION

        Describe the illustration
            -> VISION
    """

    text = str(question or "").strip().lower()

    if not text:
        return False

    visual_phrases = [
        "picture",
        "image",
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
        "describe this image",

        "what do you see",
        "what can you see",

        "objects in the picture",
        "objects shown",

        "explain the picture",
        "explain this picture",

        "explain the illustration",
        "explain this illustration",

        "explain the diagram",
        "explain this diagram",
    ]

    return any(
        phrase in text
        for phrase in visual_phrases
    )


def _language_name(language: str) -> str:
    return {
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


def _ocr_uploaded_page(
    image_path: Path,
    language: str,
) -> str:
    """
    Extract readable text from an uploaded textbook page.
    """

    import pytesseract
    from PIL import Image

    ocr_languages = {
        "en": "eng",
        "english": "eng",
        "hi": "hin",
        "hindi": "hin",
        "pa": "pan",
        "pan": "pan",
        "punjabi": "pan",
    }

    ocr_language = ocr_languages.get(
        (language or "").strip().lower(),
        "eng",
    )

    try:
        image = Image.open(image_path)

        text = pytesseract.image_to_string(
            image,
            lang=ocr_language,
        )

    except Exception as exc:
        raise RuntimeError(
            f"OCR failed: {exc}"
        ) from exc

    text = text.strip()

    if not text:
        raise RuntimeError(
            "No readable text was found in the uploaded page."
        )

    logger.info(
        "OCR extracted approximately %d characters.",
        len(text),
    )

    return text


def _explain_uploaded_page_text(
    *,
    image_path: Path,
    question: str,
    language: str,
) -> str:
    """
    Explain the textual content of an uploaded page.

    Flow:

        uploaded image
             ↓
          Tesseract
             ↓
        extracted text
             ↓
        Qwen text model
    """

    extracted_text = _ocr_uploaded_page(
        image_path=image_path,
        language=language,
    )

    answer_language = _language_name(language)

    prompt = f"""
You are a helpful Class 5 virtual teacher.

The student uploaded a textbook page and asked:

{question}

The following text was extracted from the uploaded page:

--- PAGE TEXT START ---
{extracted_text}
--- PAGE TEXT END ---

Answer the student's question using the page text.

Answer language: {answer_language}.

Use simple, clear language suitable for a Class 5 student.

Do not invent information that is not supported by the page.

If the student asks about a picture, illustration, diagram,
or other visual information that cannot be understood from
the extracted text, say that the visual part needs visual
analysis instead.

Do not show your reasoning.
Return only the final answer.
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
            "Authorization": (
                f"Bearer {settings.llm_api_key}"
            )
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
            "Text model returned an empty answer."
        )

    return answer


@router.post("/upload")
async def upload_page(
    file: UploadFile = File(...),
    question: str = Form(...),
    language: str = Form("auto"),
    response_mode: str = Form("written"),
):
    """
    Analyze one uploaded textbook page/image.

    The student's question determines the mode:

        Visual question
            -> Qwen3-VL

        Text/page question
            -> OCR + Qwen text model
    """

    image_path: Path | None = None

    try:
        question = question.strip()

        if not question:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Please enter a question "
                    "about the uploaded page."
                ),
            )

        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No file was selected.",
            )

        suffix = Path(
            file.filename
        ).suffix.lower()

        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Please upload an image file: "
                    "PNG, JPG, JPEG, or WEBP."
                ),
            )

        # --------------------------------------------------------
        # Temporary uploaded-page directory.
        # This is NOT the textbook library.
        # --------------------------------------------------------

        upload_dir = (
            Path("data/processed")
            / "vision_uploads"
        )

        upload_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_name = (
            f"{uuid.uuid4().hex}"
            f"{suffix}"
        )

        image_path = (
            upload_dir / safe_name
        )

        with image_path.open("wb") as destination:
            shutil.copyfileobj(
                file.file,
                destination,
            )

        logger.info(
            "UPLOADED PAGE: filename=%r question=%r language=%r response_mode=%r",
            file.filename,
            question,
            language,
            response_mode,
        )

        # --------------------------------------------------------
        # Decide TEXT vs VISION.
        # --------------------------------------------------------

        visual_question = (
            is_explicit_visual_question(
                question
            )
        )

        logger.info(
            "UPLOADED PAGE MODE: %s",
            "vision" if visual_question else "text",
        )

        # --------------------------------------------------------
        # VISION
        # --------------------------------------------------------

        if visual_question:
            answer = analyze_page_image(
                image_path,
                language=language,
                question=question,
            )

            audio_url = _create_answer_audio(
                answer=answer,
                language=language,
                response_mode=response_mode,
            )

            return {
                "success": True,
                "mode": "vision",
                "question": question,
                "answer": answer,
                "filename": file.filename,
                "model": settings.vision_model,
                "audio_url": audio_url,
            }

        # --------------------------------------------------------
        # TEXT / OCR
        # --------------------------------------------------------

        answer = _explain_uploaded_page_text(
            image_path=image_path,
            question=question,
            language=language,
        )

        audio_url = _create_answer_audio(
            answer=answer,
            language=language,
            response_mode=response_mode,
        )

        return {
            "success": True,
            "mode": "text",
            "question": question,
            "answer": answer,
            "filename": file.filename,
            "model": settings.llm_model,
            "audio_url": audio_url,
        }

    except HTTPException:
        raise

    except requests.RequestException as exc:
        logger.error(
            "UPLOADED PAGE LLM REQUEST FAILED:\n%s",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "The language model could not be reached "
                f"or returned an error: {exc}"
            ),
        ) from exc

    except Exception as exc:
        logger.error(
            "UPLOADED PAGE ANALYSIS FAILED:\n%s",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    finally:
        # --------------------------------------------------------
        # Uploaded page is temporary.
        # It is NOT added to the textbook/page cache.
        # --------------------------------------------------------

        if image_path is not None:
            try:
                if image_path.exists():
                    image_path.unlink()

                    logger.info(
                        "Temporary uploaded page removed: %s",
                        image_path,
                    )

            except Exception:
                logger.warning(
                    "Could not remove temporary uploaded page: %s",
                    image_path,
                )
