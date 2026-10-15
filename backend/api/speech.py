from pathlib import Path
import logging
import re
import subprocess
import tempfile
import traceback

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from backend.speech.stt import transcribe_audio
from backend.speech.vocabulary import normalize_spoken_question
from backend.ai.llm import ask_teacher
from backend.speech.tts import text_to_speech


router = APIRouter(prefix="/speech", tags=["Speech"])
logger = logging.getLogger("uvicorn.error")


# ============================================================
# LANGUAGE
# ============================================================

def normalize_language(language: str | None) -> str:
    value = (language or "auto").strip().lower()

    return {
        "english": "en",
        "eng": "en",
        "en": "en",

        "hindi": "hi",
        "hin": "hi",
        "hi": "hi",

        "punjabi": "pa",
        "pan": "pa",
        "pa": "pa",

        "auto": "auto",
        "": "auto",
    }.get(value, value)


# ============================================================
# AUDIO CONVERSION
# ============================================================

def convert_to_wav(input_file: str, output_file: str):
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            input_file,
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            output_file,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg conversion failed: "
            + (result.stderr or "unknown FFmpeg error")
        )


async def save_upload_as_temp(file: UploadFile):
    content = await file.read()

    if not content:
        raise ValueError(
            "The browser sent an empty audio file."
        )

    suffix = Path(file.filename or "").suffix.lower() or ".webm"

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    ) as f:
        f.write(content)
        return f.name


# ============================================================
# WHISPER RESULT HANDLING
# ============================================================

def _unpack_transcription_result(result):
    """
    Supports both versions of our STT function:

        "recognized text"

    and:

        ("recognized text", info)

    This lets speech.py remain compatible while STT is improved.
    """

    text = ""
    info = {}

    if isinstance(result, tuple):
        if len(result) >= 1:
            text = result[0] or ""

        if len(result) >= 2:
            info = result[1] or {}

    elif isinstance(result, dict):
        text = (
            result.get("text")
            or result.get("question")
            or ""
        )
        info = result.get("info") or result

    else:
        text = result or ""

    return str(text).strip(), info


def _info_value(info, key, default=None):
    if isinstance(info, dict):
        return info.get(key, default)

    return getattr(info, key, default)


def _looks_like_whisper_hallucination(text: str) -> bool:
    """
    Reject obvious repeated-token hallucinations.

    Example:
        "ive to ive to ive to ive to..."

    This is especially important because such text can look non-empty
    even though Whisper did not understand the student's question.
    """

    normalized = re.sub(
        r"[^a-zA-Z0-9\u0900-\u097F\u0A00-\u0A7F']+",
        " ",
        text.lower(),
    ).strip()

    if not normalized:
        return True

    tokens = normalized.split()

    # Very short transcripts are not automatically wrong, but repeated
    # phrases are a strong hallucination signal.
    if len(tokens) >= 8:
        counts = {}

        for token in tokens:
            counts[token] = counts.get(token, 0) + 1

        most_common = max(counts.values())

        if most_common / len(tokens) >= 0.65:
            return True

    # Detect repeated multi-word phrases such as:
    # "ive to ive to ive to..."
    if len(tokens) >= 6:
        for phrase_len in (2, 3, 4):
            if len(tokens) >= phrase_len * 3:
                first = tokens[:phrase_len]
                repeated = True

                for i in range(
                    phrase_len,
                    min(len(tokens), phrase_len * 4),
                    phrase_len,
                ):
                    if tokens[i:i + phrase_len] != first:
                        repeated = False
                        break

                if repeated:
                    return True

    return False


def _validate_transcription(text: str, info) -> tuple[bool, list[str]]:
    """
    Decide whether Whisper produced a question that is safe to send
    to the teacher/LLM.

    Important:
    A failed or suspicious transcription MUST NOT reach ask_teacher().
    """

    reasons = []

    if not text.strip():
        reasons.append("empty_transcription")
        return False, reasons

    reliable = _info_value(info, "reliable", None)

    info_reasons = _info_value(info, "reasons", []) or []

    if isinstance(info_reasons, str):
        info_reasons = [info_reasons]

    reasons.extend(str(x) for x in info_reasons)

    if reliable is False:
        if "unreliable_transcription" not in reasons:
            reasons.append("unreliable_transcription")

    if _looks_like_whisper_hallucination(text):
        if "possible_hallucination" not in reasons:
            reasons.append("possible_hallucination")

    # If the STT layer explicitly reports hallucination/empty audio,
    # always reject it.
    bad_flags = {
        "empty_transcription",
        "possible_hallucination",
        "audio_too_short",
        "no_speech",
    }

    if any(flag in bad_flags for flag in reasons):
        return False, reasons

    # If the current STT implementation provides an explicit reliable
    # flag, trust it.
    if reliable is False:
        return False, reasons

    return True, reasons


# ============================================================
# CLARIFICATION RESPONSE
# ============================================================

def _clarification_message(language_code: str) -> str:
    messages = {
        "en": (
            "I couldn't hear your question clearly. "
            "Please say your question again."
        ),
        "hi": (
            "मैं आपका प्रश्न स्पष्ट रूप से नहीं सुन पाया। "
            "कृपया अपना प्रश्न फिर से बोलें।"
        ),
        "pa": (
            "ਮੈਂ ਤੁਹਾਡਾ ਸਵਾਲ ਸਾਫ਼ ਤੌਰ ਤੇ ਨਹੀਂ ਸੁਣ ਸਕਿਆ। "
            "ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਸਵਾਲ ਦੁਬਾਰਾ ਬੋਲੋ।"
        ),
    }

    return messages.get(
        language_code,
        messages["en"],
    )


def _try_clarification_tts(
    message: str,
    language_code: str,
):
    try:
        audio_file = text_to_speech(
            message,
            language=language_code,
        )
        return f"/audio/{audio_file}"

    except Exception:
        logger.error(
            "CLARIFICATION TTS FAILED:\n%s",
            traceback.format_exc(),
        )
        return None


# ============================================================
# TRANSCRIBE ONLY
# ============================================================

@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    source_path = None
    wav_path = None

    try:
        source_path = await save_upload_as_temp(file)

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        ) as f:
            wav_path = f.name

        convert_to_wav(
            source_path,
            wav_path,
        )

        result = transcribe_audio(
            wav_path,
            "auto",
        )

        text, info = _unpack_transcription_result(result)

        reliable, reasons = _validate_transcription(
            text,
            info,
        )

        logger.info(
            "TRANSCRIBE RESULT: text=%r reliable=%s reasons=%s info=%s",
            text,
            reliable,
            reasons,
            info,
        )

        return {
            "success": True,
            "text": text,
            "reliable": reliable,
            "reasons": reasons,
        }

    except Exception as exc:
        logger.error(
            "TRANSCRIBE FAILED:\n%s",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    finally:
        if source_path:
            Path(source_path).unlink(
                missing_ok=True
            )

        if wav_path:
            Path(wav_path).unlink(
                missing_ok=True
            )


# ============================================================
# VOICE ASK
# ============================================================

@router.post("/ask")
async def voice_assistant(
    file: UploadFile = File(...),
    class_name: str | None = Form(None),
    subject: str | None = Form(None),
    book: str | None = Form(None),
    language: str = Form("auto"),
):
    source_path = None
    wav_path = None

    try:
        language_code = normalize_language(language)

        logger.info(
            "============================================================"
        )
        logger.info(
            "VOICE ASK: class=%r subject=%r book=%r language=%r",
            class_name,
            subject,
            book,
            language_code,
        )

        # --------------------------------------------------------
        # STEP 1 — SAVE AUDIO
        # --------------------------------------------------------

        source_path = await save_upload_as_temp(file)

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        ) as f:
            wav_path = f.name

        # --------------------------------------------------------
        # STEP 2 — CONVERT
        # --------------------------------------------------------

        convert_to_wav(
            source_path,
            wav_path,
        )

        # --------------------------------------------------------
        # STEP 3 — WHISPER
        # --------------------------------------------------------

        stt_result = transcribe_audio(
            wav_path,
            language_code,
        )

        raw_question, stt_info = _unpack_transcription_result(
            stt_result
        )

        reliable, reliability_reasons = _validate_transcription(
            raw_question,
            stt_info,
        )

        logger.info(
            "WHISPER RESULT: text=%r reliable=%s reasons=%s info=%s",
            raw_question,
            reliable,
            reliability_reasons,
            stt_info,
        )

        # --------------------------------------------------------
        # CRITICAL SAFETY GATE
        # --------------------------------------------------------
        #
        # DO NOT call Qwen when Whisper did not understand the
        # student's question.
        # --------------------------------------------------------

        if not reliable:
            message = _clarification_message(
                language_code
            )

            logger.warning(
                "VOICE QUESTION REJECTED BEFORE LLM: "
                "text=%r reasons=%s",
                raw_question,
                reliability_reasons,
            )

            audio_url = _try_clarification_tts(
                message,
                language_code,
            )

            return {
                "success": True,
                "question": "",
                "raw_question": raw_question,
                "answer": message,
                "audio_url": audio_url,
                "transcription_reliable": False,
                "transcription_reasons": reliability_reasons,
                "needs_repeat": True,
            }

        # --------------------------------------------------------
        # STEP 4 — TEXTBOOK-AWARE NORMALIZATION
        # --------------------------------------------------------

        question = raw_question
        correction_info = {
            "changed": False,
            "method": "unchanged",
            "corrections": [],
            "book": book,
            "language": language_code,
        }

        try:
            question, correction_info = normalize_spoken_question(
                raw_question,
                class_name=class_name,
                subject=subject,
                book=book,
                language=language_code,
            )

            logger.info(
                "SPEECH NORMALIZATION: raw=%r corrected=%r info=%s",
                raw_question,
                question,
                correction_info,
            )

        except Exception:
            logger.error(
                "SPEECH NORMALIZATION FAILED:\n%s",
                traceback.format_exc(),
            )

            # If optional vocabulary correction fails, the reliable
            # Whisper transcript remains the fallback.
            question = raw_question

        # --------------------------------------------------------
        # SECOND GATE
        # --------------------------------------------------------

        if not question.strip():
            message = _clarification_message(
                language_code
            )

            audio_url = _try_clarification_tts(
                message,
                language_code,
            )

            return {
                "success": True,
                "question": "",
                "raw_question": raw_question,
                "answer": message,
                "audio_url": audio_url,
                "transcription_reliable": False,
                "transcription_reasons": [
                    "empty_after_normalization"
                ],
                "needs_repeat": True,
            }

        # --------------------------------------------------------
        # STEP 5 — ONLY NOW ASK THE TEACHER
        # --------------------------------------------------------

        logger.info(
            "VOICE QUESTION ACCEPTED: %r",
            question,
        )

        answer = ask_teacher(
            question=question,
            class_name=class_name,
            subject=subject,
            book=book,
            language=language_code,
        )

        # --------------------------------------------------------
        # STEP 6 — TTS ANSWER
        # --------------------------------------------------------

        audio_url = None

        try:
            audio_file = text_to_speech(
                answer,
                language=language_code,
            )

            audio_url = f"/audio/{audio_file}"

        except Exception:
            logger.error(
                "TTS FAILED:\n%s",
                traceback.format_exc(),
            )

        logger.info(
            "VOICE ASK COMPLETE: question=%r",
            question,
        )

        return {
            "success": True,
            "raw_question": raw_question,
            "question": question,
            "corrected": question != raw_question,
            "correction": correction_info,
            "answer": answer,
            "audio_url": audio_url,
            "transcription_reliable": True,
            "transcription_reasons": reliability_reasons,
            "needs_repeat": False,
        }

    except Exception as exc:
        logger.error(
            "VOICE ASK FAILED:\n%s",
            traceback.format_exc(),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    finally:
        if source_path:
            Path(source_path).unlink(
                missing_ok=True
            )

        if wav_path:
            Path(wav_path).unlink(
                missing_ok=True
            )