# Architecture

## Frontend

Location:

frontend/

Main JavaScript:

frontend/app.js

Responsibilities:

- class selection
- subject selection
- language selection
- textbook selection
- question submission
- streaming response handling
- answer display
- speech controls
- visual teacher controls
- textbook upload UI

---

## Backend

Location:

backend/

Framework:

FastAPI

Entry point:

backend/main.py

---

## API

Important endpoints:

GET /health

POST /api/chat

GET /api/books

Additional endpoints may exist.

---

## RAG

Responsibilities:

- load textbook
- split textbook content
- generate embeddings
- store vectors
- retrieve relevant content
- constrain retrieval to selected textbook

---

## Vector Database

Qdrant

Docker service:

qdrant

Internal URL:

[http://qdrant:6333](http://qdrant:6333)

Collection:

class5_books

---

## Embeddings

FastEmbed

Model:

intfloat/multilingual-e5-large

Runtime:

ONNX Runtime GPU

Providers:

CUDAExecutionProvider
CPUExecutionProvider

---

## LLM

LM Studio

Model:

qwen/qwen3.5-9b

Host URL:

[http://127.0.0.1:1234/v1](http://127.0.0.1:1234/v1)

Docker URL:

[http://host.docker.internal:1234/v1](http://host.docker.internal:1234/v1)

---

## Speech

STT:

Faster-Whisper

TTS:

Piper

---

## OCR

Tesseract OCR

Languages:

English
Hindi
Punjabi

---

## Docker

Services:

virtual-teacher
qdrant

Application port:

8000

Qdrant ports:

6333

6334
