import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.ai.llm import stream_teacher
from backend.models.schemas import ChatRequest
from backend.speech.tts import text_to_speech


router = APIRouter(prefix="/api/chat", tags=["Chat"])


def normalize_tts_language(language: str | None) -> str:
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
    }.get(value, "en")


def _ndjson(payload: dict) -> str:
    """One JSON event per line for simple browser streaming."""
    return json.dumps(
        payload,
        ensure_ascii=False,
    ) + "\n"


@router.post("")
def chat(request: ChatRequest):
    """
    Stream the LLM answer to the browser as NDJSON.

    Event types:
      chunk -> incremental answer text
      done  -> final answer + optional audio URL
      error -> error message
    """

    def event_stream():
        answer_parts = []

        try:
            for chunk in stream_teacher(
                question=request.question,
                class_name=request.class_name,
                subject=request.subject,
                book=request.book,
                language=request.language,
            ):
                if not chunk:
                    continue

                answer_parts.append(chunk)

                yield _ndjson(
                    {
                        "type": "chunk",
                        "text": chunk,
                    }
                )

            answer = "".join(answer_parts).strip()

            if not answer:
                answer = "I couldn't generate an answer from the selected textbook."

            # Send the completed text immediately. The browser can mark the
            # written answer as ready without waiting for TTS.
            yield _ndjson(
                {
                    "type": "done",
                    "answer": answer,
                    "language": request.language,
                    "audio_url": None,
                }
            )

            # Generate speech only after the text has been delivered.
            # If TTS takes extra time, the student can already read the answer.
            if request.response_mode in {"spoken", "both"}:
                try:
                    filename = text_to_speech(
                        answer,
                        language=normalize_tts_language(request.language),
                    )
                    audio_url = f"/audio/{filename}"

                    yield _ndjson(
                        {
                            "type": "audio",
                            "audio_url": audio_url,
                        }
                    )
                except Exception as exc:
                    # TTS failure must never destroy the written answer.
                    print(f"TTS warning: {exc}")

        except Exception as exc:
            print(f"CHAT STREAM ERROR: {exc}")
            yield _ndjson(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )