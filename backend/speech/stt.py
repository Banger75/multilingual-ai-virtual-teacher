from __future__ import annotations

import re
from functools import lru_cache

from backend.config import settings


# ============================================================
# LANGUAGE NORMALIZATION
# ============================================================

def normalize_whisper_language(language: str | None) -> str | None:
    value = (language or "auto").strip().lower()

    aliases = {
        "english": "en",
        "eng": "en",
        "en": "en",

        "hindi": "hi",
        "hin": "hi",
        "hi": "hi",

        "punjabi": "pa",
        "pan": "pa",
        "pa": "pa",

        "auto": None,
        "": None,
    }

    return aliases.get(
        value,
        value if len(value) in (2, 3) else None,
    )


# ============================================================
# WHISPER MODEL
# ============================================================

@lru_cache(maxsize=1)
def get_whisper_model():
    from faster_whisper import WhisperModel

    print(
        f"Loading Whisper model: {settings.whisper_model}"
    )

    return WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


# ============================================================
# INITIAL PROMPT
# ============================================================

def _build_initial_prompt(
    vocabulary: list[str] | None = None,
    language: str | None = None,
) -> str | None:
    """
    Build a small textbook-aware prompt for Whisper.

    This is deliberately limited in size. A huge vocabulary prompt
    can make recognition worse.
    """

    if not vocabulary:
        return None

    unique_terms = []
    seen = set()

    for term in vocabulary:
        term = str(term).strip()

        if not term:
            continue

        if len(term) < 4:
            continue

        key = term.casefold()

        if key in seen:
            continue

        seen.add(key)
        unique_terms.append(term)

    if not unique_terms:
        return None

    # Prefer distinctive / multi-word terms.
    unique_terms.sort(
        key=lambda value: (
            " " not in value,
            -len(value),
        )
    )

    unique_terms = unique_terms[:80]

    language_name = {
        "en": "English",
        "hi": "Hindi",
        "pa": "Punjabi",
    }.get(
        normalize_whisper_language(language)
    )

    if language_name:
        prefix = (
            f"This is a {language_name} school textbook. "
            "The student may mention these textbook terms: "
        )
    else:
        prefix = (
            "This is a multilingual school textbook. "
            "The student may mention these textbook terms: "
        )

    return prefix + ", ".join(unique_terms)


# ============================================================
# REPETITION / HALLUCINATION DETECTOR
# ============================================================

def _has_repeated_phrase(
    text: str,
    minimum_repetitions: int = 4,
) -> bool:
    """
    Detect obvious Whisper repetition hallucinations.

    Example:
        "ive to ive to ive to ive to ive to ..."

    This is treated as invalid speech recognition.
    """

    words = re.findall(
        r"[\w\u0900-\u097F\u0A00-\u0A7F'-]+",
        text.lower(),
        re.UNICODE,
    )

    if len(words) < 8:
        return False

    # Look for repeated 1-5 word phrases.
    for phrase_size in range(1, 6):

        if len(words) < phrase_size * minimum_repetitions:
            continue

        counts: dict[tuple[str, ...], int] = {}

        for index in range(
            len(words) - phrase_size + 1
        ):
            phrase = tuple(
                words[index:index + phrase_size]
            )

            counts[phrase] = (
                counts.get(phrase, 0) + 1
            )

        highest = max(
            counts.values(),
            default=0,
        )

        if highest >= minimum_repetitions:
            return True

    return False


def _is_suspicious_transcription(
    text: str,
    average_logprob: float | None,
    maximum_compression_ratio: float | None,
) -> tuple[bool, list[str]]:
    """
    Decide whether a Whisper result should be retried.
    """

    reasons = []

    if not text.strip():
        reasons.append("empty_transcription")

    # Your actual bad result had compression_ratio=25.7.
    if (
        maximum_compression_ratio is not None
        and maximum_compression_ratio > 2.8
    ):
        reasons.append("possible_hallucination")

    # Repeated phrase detection catches cases where compression
    # ratio alone is not enough.
    if _has_repeated_phrase(text):
        reasons.append("repeated_phrase")

    # Conservative threshold.
    if (
        average_logprob is not None
        and average_logprob < -1.20
    ):
        reasons.append("low_log_probability")

    return bool(reasons), reasons


# ============================================================
# ONE WHISPER PASS
# ============================================================

def _transcribe_once(
    model,
    audio_file: str,
    forced_language: str | None,
    initial_prompt: str | None,
):
    """
    Run one independent Whisper transcription.
    """

    segments, info = model.transcribe(
        audio_file,

        language=forced_language,

        beam_size=5,
        best_of=5,

        temperature=0.0,

        condition_on_previous_text=False,

        vad_filter=True,

        vad_parameters={
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 300,
        },

        initial_prompt=initial_prompt,

        no_speech_threshold=0.6,

        log_prob_threshold=-1.0,

        compression_ratio_threshold=2.4,
    )

    collected = []

    for segment in segments:

        text = (
            segment.text or ""
        ).strip()

        if not text:
            continue

        collected.append(
            {
                "text": text,
                "avg_logprob": getattr(
                    segment,
                    "avg_logprob",
                    None,
                ),
                "no_speech_prob": getattr(
                    segment,
                    "no_speech_prob",
                    None,
                ),
                "compression_ratio": getattr(
                    segment,
                    "compression_ratio",
                    None,
                ),
            }
        )

    text = " ".join(
        item["text"]
        for item in collected
    ).strip()

    logprobs = [
        item["avg_logprob"]
        for item in collected
        if isinstance(
            item["avg_logprob"],
            (int, float),
        )
    ]

    no_speech_values = [
        item["no_speech_prob"]
        for item in collected
        if isinstance(
            item["no_speech_prob"],
            (int, float),
        )
    ]

    compression_values = [
        item["compression_ratio"]
        for item in collected
        if isinstance(
            item["compression_ratio"],
            (int, float),
        )
    ]

    average_logprob = (
        sum(logprobs) / len(logprobs)
        if logprobs
        else None
    )

    maximum_no_speech_probability = (
        max(no_speech_values)
        if no_speech_values
        else None
    )

    maximum_compression_ratio = (
        max(compression_values)
        if compression_values
        else None
    )

    suspicious, reasons = _is_suspicious_transcription(
        text,
        average_logprob,
        maximum_compression_ratio,
    )

    detected_language = getattr(
        info,
        "language",
        None,
    )

    language_probability = getattr(
        info,
        "language_probability",
        None,
    )

    diagnostics = {
        "reliable": not suspicious,
        "reasons": reasons,

        "detected_language": detected_language,
        "language_probability": language_probability,

        "forced_language": forced_language,

        "average_logprob": average_logprob,

        "maximum_no_speech_probability": (
            maximum_no_speech_probability
        ),

        "maximum_compression_ratio": (
            maximum_compression_ratio
        ),

        "segment_count": len(collected),

        "initial_prompt_used": bool(
            initial_prompt
        ),
    }

    return text, diagnostics


# ============================================================
# TWO-PASS TRANSCRIPTION
# ============================================================

def transcribe_audio_with_info(
    audio_file: str,
    language: str = "auto",
    vocabulary: list[str] | None = None,
) -> tuple[str, dict]:
    """
    Two-pass Whisper transcription.

    PASS 1:
        Uses textbook vocabulary.

    PASS 2:
        Used only when Pass 1 is suspicious.
        Does NOT use textbook vocabulary.

    This prevents a bad Whisper hallucination from going
    directly to the teacher LLM.
    """

    model = get_whisper_model()

    forced_language = normalize_whisper_language(
        language
    )

    # --------------------------------------------------------
    # PASS 1
    # --------------------------------------------------------

    initial_prompt = _build_initial_prompt(
        vocabulary=vocabulary,
        language=forced_language,
    )

    text1, info1 = _transcribe_once(
        model=model,
        audio_file=audio_file,
        forced_language=forced_language,
        initial_prompt=initial_prompt,
    )

    print(
        "Whisper PASS 1: "
        f"reliable={info1['reliable']}, "
        f"reasons={info1['reasons']}, "
        f"text={text1!r}"
    )

    # Good result → use it immediately.
    if info1["reliable"] and text1.strip():

        info1["pass_used"] = 1
        info1["retry_performed"] = False

        return text1, info1

    # --------------------------------------------------------
    # PASS 2
    #
    # No initial prompt.
    # This gives Whisper an independent attempt.
    # --------------------------------------------------------

    print(
        "Whisper PASS 1 suspicious. "
        "Running PASS 2 without textbook prompt."
    )

    text2, info2 = _transcribe_once(
        model=model,
        audio_file=audio_file,
        forced_language=forced_language,
        initial_prompt=None,
    )

    print(
        "Whisper PASS 2: "
        f"reliable={info2['reliable']}, "
        f"reasons={info2['reasons']}, "
        f"text={text2!r}"
    )

    # Good second result → use it.
    if info2["reliable"] and text2.strip():

        info2["pass_used"] = 2
        info2["retry_performed"] = True

        # Keep useful information from Pass 1.
        info2["first_pass_text"] = text1
        info2["first_pass_reasons"] = info1[
            "reasons"
        ]

        return text2, info2

    # --------------------------------------------------------
    # BOTH PASSES FAILED
    # --------------------------------------------------------

    final_text = (
        text2.strip()
        if text2.strip()
        else text1.strip()
    )

    final_info = info2

    final_info["reliable"] = False
    final_info["retry_performed"] = True
    final_info["pass_used"] = 2

    final_info["first_pass_text"] = text1
    final_info["first_pass_reasons"] = info1[
        "reasons"
    ]

    # Do not allow a hallucinated repeated phrase to be
    # passed further into the teacher pipeline.
    if _has_repeated_phrase(final_text):

        final_text = ""

        if "repeated_phrase" not in final_info[
            "reasons"
        ]:
            final_info["reasons"].append(
                "repeated_phrase"
            )

    print(
        "Whisper BOTH PASSES FAILED. "
        f"final_text={final_text!r}"
    )

    return final_text, final_info


# ============================================================
# BACKWARD-COMPATIBLE FUNCTION
# ============================================================

def transcribe_audio(
    audio_file: str,
    language: str = "auto",
    vocabulary: list[str] | None = None,
) -> str:

    text, _info = transcribe_audio_with_info(
        audio_file,
        language=language,
        vocabulary=vocabulary,
    )

    return text