# AGENTS.md
# Subject Specific AI Virtual Teacher
# Development Instructions for Codex

---

# 1. PROJECT IDENTITY

Project name:

Subject Specific AI Virtual Teacher

Purpose:

This application is a multilingual, subject-specific AI virtual teacher
designed to teach school students using their selected textbooks.

The system must prioritize textbook-grounded answers over general
LLM knowledge.

This is NOT intended to be a general-purpose chatbot.

---

# 2. CORE PRODUCT REQUIREMENT

The most important requirement is:

THE VIRTUAL TEACHER MUST ANSWER FROM THE SELECTED TEXTBOOK.

The answer must be grounded in the textbook content retrieved for:

- selected class
- selected subject
- selected textbook
- relevant lesson/chapter

The LLM must not freely substitute its general knowledge for missing
textbook information.

If the textbook does not contain enough information to answer a question,
the system should not invent an answer.

---

# 3. CURRENT ARCHITECTURE

The application currently follows this architecture:

Student Browser
    |
    v
Frontend
    |
    | HTTP
    v
FastAPI
    |
    +----------------------+
    |                      |
    v                      v
RAG / Qdrant            LM Studio
    |                      |
    v                      v
FastEmbed GPU            Qwen LLM
    |
    v
Textbook embeddings


Supporting components:

- FastAPI
- Uvicorn
- Qdrant
- FastEmbed
- ONNX Runtime GPU
- NVIDIA CUDA
- LM Studio
- Qwen
- Faster-Whisper
- Piper TTS
- Tesseract OCR
- PyMuPDF
- Docker Compose

---

# 4. ENVIRONMENT

The application runs primarily through Docker.

Current important services:

virtual-teacher
qdrant

Docker service names must not be changed casually.

Current Qdrant service:

qdrant

Current application service:

virtual-teacher

Current container names:

virtual-teacher-app
virtual-teacher-qdrant

---

# 5. NETWORKING RULES

IMPORTANT:

Host and Docker networking are different.

LM Studio runs on Windows host.

From Windows:

http://127.0.0.1:1234/v1

From inside Docker:

http://host.docker.internal:1234/v1

Qdrant is accessed from the application container through:

http://qdrant:6333

DO NOT replace these Docker networking addresses with
127.0.0.1 inside the application container.

127.0.0.1 inside Docker refers to the application container itself.

---

# 6. LLM

Current LLM provider:

LM Studio

Current model:

qwen/qwen3.5-9b

Current API style:

OpenAI-compatible API

Current Docker LLM URL:

http://host.docker.internal:1234/v1

Do not change the LLM provider, model, or endpoint without
explicitly checking compatibility with the existing application.

The application must remain compatible with an OpenAI-compatible
API interface.

---

# 7. EMBEDDINGS

Current embedding model:

intfloat/multilingual-e5-large

Current embedding implementation:

FastEmbed

GPU runtime:

ONNX Runtime GPU

Expected providers include:

CUDAExecutionProvider
CPUExecutionProvider

GPU acceleration is intentional.

Do not replace the embedding model or embedding framework without
considering:

- existing Qdrant vectors
- vector dimensions
- multilingual retrieval quality
- indexing compatibility
- retrieval accuracy

Changing the embedding model may require rebuilding the vector collection.

---

# 8. GPU

The application is designed to use NVIDIA GPU acceleration.

Current working environment:

NVIDIA RTX 5060
CUDA 13.1.x
ONNX Runtime GPU
CUDAExecutionProvider

The Docker image currently uses a CUDA 13.1-compatible runtime.

Do not upgrade or downgrade CUDA simply because a newer version exists.

Before changing CUDA versions, verify compatibility between:

- NVIDIA driver
- CUDA container
- ONNX Runtime GPU
- FastEmbed
- application dependencies

---

# 9. QDRANT

Qdrant is the vector database.

Current service:

qdrant

Current application URL:

http://qdrant:6333

Current collection:

school_books

Do not delete or recreate the collection automatically.

Before changing:

- collection name
- vector size
- distance metric
- embedding model
- payload schema

inspect the existing implementation and indexed data.

Never destroy existing textbook data without explicit approval.

---

# 10. TEXTBOOK SELECTION

The frontend allows the student to select:

- Class
- Subject
- Language
- Textbook

The selected textbook is a critical retrieval constraint.

The system must not accidentally retrieve content from:

- another class
- another subject
- another textbook

unless the application explicitly supports that behavior.

Example:

Class 5
Subject English
Book English_Class 5.pdf

must retrieve English Class 5 textbook content.

---

# 11. RAG REQUIREMENTS

RAG stands for Retrieval-Augmented Generation.

The expected flow is:

Student Question
        |
        v
Selected Class
        |
        v
Selected Subject
        |
        v
Selected Book
        |
        v
Retrieve relevant textbook chunks
        |
        v
Provide textbook context to LLM
        |
        v
Generate answer
        |
        v
Return answer to student

The LLM should not answer textbook questions purely from memory.

Retrieval quality is more important than merely producing fluent answers.

---

# 12. TEXTBOOK GROUNDING

The system should prefer:

- facts explicitly present in the textbook
- wording supported by the textbook
- explanations derived from the retrieved textbook context

The system should avoid:

- invented facts
- unsupported details
- information from unrelated books
- internet knowledge unless explicitly requested and supported
- model-memory substitutions

If evidence is insufficient, the system should indicate that the
textbook content does not provide enough information.

---

# 13. LANGUAGE SUPPORT

The application is multilingual.

Current important languages include:

- English
- Hindi
- Punjabi

Language selection must be respected.

The answer language should normally follow the selected language
and application configuration.

Do not remove multilingual support when modifying unrelated functionality.

---

# 14. SPEECH

Speech functionality includes:

STT:
Faster-Whisper

TTS:
Piper

Current Whisper configuration:

WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

Do not move Whisper to GPU without explicit testing.

Speech changes must not break the text-only chat path.

---

# 15. OCR

The application uses Tesseract OCR.

Current language packages include:

- English
- Hindi
- Punjabi

OCR is important for textbook/document processing.

Do not remove OCR dependencies because the current PDF happens
to contain selectable text.

Some future textbooks may be image-based.

---

# 16. FRONTEND

The main frontend JavaScript file is:

frontend/app.js

The frontend communicates with FastAPI.

Important UI elements include:

- class selector
- subject selector
- language selector
- textbook selector
- question input
- Ask Teacher button
- recording controls
- answer area
- audio area
- teacher state
- visual board
- upload controls

Do not rename existing HTML IDs without checking all JavaScript references.

Before changing frontend event handling, verify:

- event listeners
- DOM element IDs
- API endpoints
- streaming response handling
- error handling
- loading state

---

# 17. CHAT API

Current important endpoint:

POST /api/chat

The application currently supports streaming responses.

The response can contain multiple JSON lines such as:

{"type":"chunk","text":"..."}

followed by:

{"type":"done","answer":"...","language":"English","audio_url":null}

Do not convert this into a normal single JSON response without
explicitly checking and updating the frontend.

The frontend must correctly handle streaming responses.

---

# 18. HEALTH CHECK

Current endpoint:

GET /health

Expected successful response contains:

status = ok

Example:

{
    "status": "ok",
    "llm": "http://host.docker.internal:1234/v1",
    "qdrant": "http://qdrant:6333"
}

After backend changes, verify:

curl.exe http://localhost:8000/health

---

# 19. QUESTION BANK

The application has a separate oral-test question bank system.

Important file:

backend/ai/question_bank.py

The question bank must be:

- textbook-grounded
- deterministicly validated
- free of duplicate questions
- supported by textbook evidence
- appropriate for the selected lesson
- appropriate for the requested difficulty

The question-bank implementation must not silently affect the
existing written question-answer feature.

---

# 20. QUESTION BANK VALIDATION

The question-bank validation pipeline includes:

1. Validate generated JSON.
2. Validate question structure.
3. Validate difficulty.
4. Detect duplicate questions.
5. Verify evidence exists in textbook.
6. Verify answer is supported by evidence.

The validation is intentionally deterministic.

Do not remove deterministic validation merely because the LLM
produces apparently good answers.

---

# 21. EVIDENCE VALIDATION

Evidence must actually occur in the textbook.

Function:

_evidence_exists()

The evidence is normalized before comparison.

Evidence should not be accepted merely because it sounds plausible.

---

# 22. TEXT NORMALIZATION

Function:

_normalize_text()

Current normalization handles:

- lowercase conversion
- curly apostrophes
- quotation marks
- dashes
- Unicode minus
- ligatures
- whitespace normalization

Normalization must not alter the actual semantic words.

Example:

Milkha Singh’s

and

Milkha Singh's

should be comparable.

Likewise punctuation and line-break differences should not cause
false validation failures.

---

# 23. ANSWER SUPPORT RULE

Function:

_answer_supported()

Current validation strategy:

LEVEL 1:
If the normalized answer is directly contained in the normalized
evidence, accept it.

LEVEL 2:
If the answer is not directly contained, compare meaningful words.

Meaningful answer words are words of at least 3 characters.

Punctuation must not affect word matching.

Use actual word extraction rather than raw whitespace splitting.

Current fallback threshold:

80% meaningful answer-word coverage.

Current calculation:

required = max(
    2,
    math.ceil(len(answer_words) * 0.80),
)

This rule intentionally replaced the earlier 60% threshold.

Do not change this threshold without testing validation accuracy.

---

# 24. ANSWER SUPPORT EXAMPLES

Supported:

Evidence:
"Milkha Singh showed patience, courage, devotion and hard work."

Answer:
"patience courage devotion hard work"

Expected:

True

Unsupported:

Evidence:
"Milkha Singh showed patience, courage, devotion and hard work."

Answer:
"Milkha Singh was a famous scientist who discovered electricity."

Expected:

False

Partially supported:

Evidence:
"Milkha Singh showed patience, courage, devotion and hard work."

Answer:
"Milkha Singh showed patience, courage and hard work."

Expected:

True

Punctuation should not cause false rejection.

---

# 25. IMPORTANT ACCURACY PRINCIPLE

Never optimize for:

"the LLM generated something plausible."

Optimize for:

"the answer is supported by the selected textbook."

The application is an educational system.

Accuracy and textbook grounding are more important than creative
or conversational output.

---

# 26. CHANGE MANAGEMENT

Before making a significant change:

1. Inspect the existing implementation.
2. Identify dependencies.
3. Make the smallest reasonable change.
4. Run a focused test.
5. Run relevant integration tests.
6. Check application logs.
7. Check the health endpoint.
8. Check the affected frontend functionality.
9. Report exactly what changed.

Do not rewrite entire files unnecessarily.

Do not refactor unrelated code during a bug fix.

---

# 27. NEVER DO THESE WITHOUT EXPLICIT APPROVAL

Never:

- delete Qdrant data
- change the embedding model
- change the vector dimension
- change the collection name
- replace the LLM
- remove textbook filtering
- remove evidence validation
- remove answer-support validation
- remove multilingual support
- remove streaming
- remove OCR
- remove STT/TTS
- rewrite frontend/app.js unnecessarily
- change Docker networking without testing
- change CUDA versions without compatibility verification
- upgrade large dependency groups merely for convenience

---

# 28. TESTING REQUIREMENTS

Backend changes should include relevant tests.

Minimum health test:

curl.exe http://localhost:8000/health

Chat test:

POST /api/chat

Use a known textbook question.

Example:

"Milkha Singh had what qualities?"

Expected answer should be grounded in:

English_Class 5.pdf

Question-bank evaluator tests should include:

- exact supported answer
- punctuation variation
- whitespace variation
- case variation
- partially supported answer
- unsupported answer
- duplicate question
- missing evidence

---

# 29. DOCKER REQUIREMENTS

The application is expected to run through:

docker compose

Typical commands:

docker compose ps

docker compose logs --tail=100 virtual-teacher

docker compose logs --tail=100 qdrant

docker compose build virtual-teacher

docker compose up -d

Do not unnecessarily use --no-cache because the CUDA image is large.

---

# 30. DEBUGGING ORDER

When the application fails:

1. Check docker compose ps.
2. Check virtual-teacher logs.
3. Check qdrant logs if retrieval is involved.
4. Check /health.
5. Check LM Studio /v1/models.
6. Check GPU providers if embeddings fail.
7. Check API endpoint directly.
8. Only then debug frontend JavaScript.

Do not assume a frontend failure is a frontend bug until
the backend endpoint has been tested directly.

---

# 31. FRONTEND DEBUGGING

When the Ask Teacher button fails:

Check:

1. DOM element exists.
2. Click handler is attached.
3. askTeacher() is called.
4. Request is sent.
5. HTTP status is successful.
6. Response body is received.
7. Streaming chunks are parsed correctly.
8. done message is processed.
9. answer is displayed.

Do not modify the API merely because the frontend cannot display
a response.

---

# 32. CODE STYLE

Prefer:

- clear Python
- small functions
- explicit validation
- meaningful variable names
- comments for important decisions
- minimal changes
- deterministic behavior

Avoid:

- unnecessary abstractions
- giant rewrites
- hidden global state
- duplicated logic
- magic constants without explanation

---

# 33. DEPENDENCY CHANGES

Before adding a dependency:

1. Check whether an existing dependency already provides the feature.
2. Check Python compatibility.
3. Check Docker compatibility.
4. Check GPU compatibility if applicable.
5. Update pyproject.toml.
6. Update uv.lock appropriately.
7. Rebuild and test.

Do not install random packages directly into the running container
as a permanent solution.

Dependencies belong in project configuration.

---

# 34. CURRENT PRIORITY

The current project priority is:

1. Stable textbook retrieval.
2. Accurate textbook-grounded answers.
3. Stable question-bank generation.
4. Reliable deterministic evaluation.
5. Reliable frontend interaction.
6. Speech functionality.
7. Visual teacher/whiteboard.
8. Further educational features.

Do not sacrifice earlier priorities for later features.

---

# 35. GENERAL CODEX RULE

Before changing code, understand why the existing code exists.

If a requested change conflicts with this document:

STOP and explain the conflict.

Do not silently choose a different architecture.

If there is uncertainty about an important architectural decision,
ask before making a destructive or broad change.

---

# 36. DEFINITION OF DONE

A feature is not complete merely because the code compiles.

A feature is complete when:

- implementation works
- existing functionality still works
- relevant tests pass
- Docker application starts
- /health works
- relevant API endpoint works
- frontend works when applicable
- logs show no unexpected errors
- textbook-grounding requirements remain intact

---

# END OF AGENTS.md