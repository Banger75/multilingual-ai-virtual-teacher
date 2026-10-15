from __future__ import annotations

from collections.abc import Iterator

from langchain_openai import ChatOpenAI

from backend.config import settings
from backend.ai.prompts import teacher_prompt
from backend.rag.retriever import retrieve_context


# ============================================================
# LOCAL LM STUDIO / QWEN
# ============================================================

llm = ChatOpenAI(
    model=settings.llm_model,
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    temperature=0.2,
    max_tokens=300,
    extra_body={
        "Chat_templete_kwargs": {
            "enable_thinking": False
        }
    },
)


NO_CONTEXT_ANSWER = (
    "I couldn't find this information in the selected textbook."
)

NO_GENERATED_ANSWER = (
    "I couldn't generate an answer from the selected textbook."
)


def _fallback_answer(language: str, question: str, *, missing_context: bool) -> str:
    value = (language or "auto").strip().lower()
    if value == "auto":
        if any("\u0a00" <= character <= "\u0a7f" for character in question):
            value = "pa"
        elif any("\u0900" <= character <= "\u097f" for character in question):
            value = "hi"
    if value in {"hi", "hin", "hindi"}:
        return "चुनी हुई पाठ्यपुस्तक में इस प्रश्न का उत्तर देने के लिए पर्याप्त जानकारी नहीं मिली।"
    if value in {"pa", "pan", "punjabi"}:
        return "ਚੁਣੀ ਹੋਈ ਪਾਠ ਪੁਸਤਕ ਵਿੱਚ ਇਸ ਸਵਾਲ ਦਾ ਜਵਾਬ ਦੇਣ ਲਈ ਲੋੜੀਂਦੀ ਜਾਣਕਾਰੀ ਨਹੀਂ ਮਿਲੀ।"
    return NO_CONTEXT_ANSWER if missing_context else NO_GENERATED_ANSWER


# ============================================================
# RETRIEVE TEXTBOOK CONTEXT
# ============================================================

def _get_context(
    question: str,
    class_name=None,
    subject=None,
    book=None,
):
    """
    Retrieve relevant textbook chunks from Qdrant.
    """

    results = retrieve_context(
        question,
        limit=5,
        class_name=class_name,
        subject=subject,
        book=book,
    )

    if not results:
        return None

    context_parts = []

    for result in results:
        payload = result.payload or {}

        text = payload.get("text", "")

        if text:
            context_parts.append(text)

    context = "\n\n---\n\n".join(context_parts)

    if not context.strip():
        return None

    return context


# ============================================================
# BUILD TEACHER PROMPT
# ============================================================

def _build_messages(
    question: str,
    context: str,
    language: str,
):
    """
    Build the final teacher prompt.

    /no_think is important for qwen3-8b.
    It prevents the model from generating a reasoning stream.
    """

    answer_language = normalize_answer_language(language)

    messages = teacher_prompt.invoke(
        {
            "question": question,
            "context": context,
            "language": answer_language,
        }
    )

    # Add /no_think to the final user message.
    #
    # LangChain messages are mutable message objects, so we create
    # a clean copy with the command appended to the user message.
    for message in messages.messages:
        if getattr(message, "type", "") == "human":
            message.content = (
                str(message.content).rstrip()
                + "\n\n/no_think"
            )
            break

    return messages


# ============================================================
# NORMAL / NON-STREAMING TEACHER
# ============================================================

def ask_teacher(
    question: str,
    class_name=None,
    subject=None,
    book=None,
    language="auto",
) -> str:
    """
    Generate a complete teacher answer.
    """

    context = _get_context(
        question,
        class_name=class_name,
        subject=subject,
        book=book,
    )

    if context is None:
        return _fallback_answer(language, question, missing_context=True)

    messages = _build_messages(
        question,
        context,
        language,
    )

    response = llm.invoke(messages)

    answer = extract_answer(response)

    if not answer:
        return _fallback_answer(language, question, missing_context=False)

    return answer


# ============================================================
# STREAMING TEACHER
# ============================================================

def stream_teacher(
    question: str,
    class_name=None,
    subject=None,
    book=None,
    language="auto",
) -> Iterator[str]:
    """
    Stream the clean final answer from Qwen.

    Qwen3-8B is instructed with /no_think, so reasoning
    content should not appear in the student response.
    """

    context = _get_context(
        question,
        class_name=class_name,
        subject=subject,
        book=book,
    )

    if context is None:
        yield _fallback_answer(language, question, missing_context=True)
        return

    messages = _build_messages(
        question,
        context,
        language,
    )

    generated_anything = False

    for chunk in llm.stream(messages):

        content = getattr(chunk, "content", "")

        # Normal string response
        if isinstance(content, str):

            text = content

        # Structured content blocks
        elif isinstance(content, list):

            parts = []

            for item in content:

                if isinstance(item, str):
                    parts.append(item)

                elif isinstance(item, dict):

                    item_text = item.get("text")

                    if item_text:
                        parts.append(str(item_text))

            text = "".join(parts)

        else:

            text = str(content or "")

        if text:

            generated_anything = True

            yield text

    if not generated_anything:
        yield _fallback_answer(language, question, missing_context=False)


# ============================================================
# SAFE ANSWER EXTRACTION
# ============================================================

def extract_answer(response) -> str:
    """
    Extract only the actual answer.

    We intentionally DO NOT use reasoning_content.
    """

    content = getattr(response, "content", "")

    if isinstance(content, str):

        return content.strip()

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):

                text = item.get("text")

                if text:
                    parts.append(str(text))

        return "".join(parts).strip()

    return str(content or "").strip()


# ============================================================
# ANSWER LANGUAGE
# ============================================================

def normalize_answer_language(language: str) -> str:

    value = (language or "auto").strip().lower()

    aliases = {

        "en": "English",
        "english": "English",

        "hi": "Hindi",
        "hindi": "Hindi",

        "pa": "Punjabi",
        "pan": "Punjabi",
        "punjabi": "Punjabi",

        "auto": "same language as the student question",
    }

    return aliases.get(value, language)
