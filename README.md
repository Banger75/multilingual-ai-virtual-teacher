# Multilingual AI Virtual Teacher

**Portfolio source preview — development project, not a verified production release.**

A subject-specific, multilingual virtual teaching application that combines FastAPI, retrieval-augmented generation (RAG), Qdrant, locally served large language models, and optional speech and avatar features. The interface is designed for English, Hindi, and Punjabi learning workflows.

## What the project includes

- Subject- and textbook-oriented question answering with document retrieval.
- FastAPI routes and frontend UI for interactive questions and answers.
- Qdrant vector retrieval and embedding integration.
- Speech-to-text and text-to-speech integrations, with textbook-aware vocabulary correction.
- Experimental question-generation, vision, and avatar-related modules.

Features listed here are identified in the source, not independently validated through a working deployment. Some optional modules require separate software or model assets.

## Architecture

```text
Student (browser)
    | text / microphone
    v
Frontend (HTML/CSS/JavaScript)
    | HTTP requests
    v
FastAPI backend
    |-- textbook processing -> embeddings -> Qdrant
    |-- retrieval -> prompt -> LM Studio / OpenAI-compatible LLM
    |-- speech input -> Faster-Whisper / normalization
    |-- speech output -> Piper / optional IndicF5 integration
    |-- optional vision and avatar modules
    v
Answer / media response
```

## Technology

Python 3.11–3.12, FastAPI, LangChain, Qdrant, LM Studio-compatible LLM API, multilingual embeddings, Faster-Whisper, Piper, Docker, JavaScript. GPU-oriented dependencies are present in the original configuration.

## Repository layout

- `backend/` — API, RAG, speech, vision, configuration, and application logic.
- `frontend/` — interactive browser application.
- `tests/` — development tests and smoke-test scripts.
- `docs/` — implementation notes.
- `ARCHITECTURE.md` — component responsibilities and services.
- `.env.example` — non-secret configuration template.
- `GITHUB_PUBLICATION_NOTES.md` — **read this before attempting installation or publishing**.

## Development setup (requires local dependencies)

1. Install Python 3.11 or 3.12 and an appropriate environment manager.
2. Set up a running Qdrant instance and an OpenAI-compatible local LLM server (for example LM Studio).
3. Copy `.env.example` to `.env` and adapt host URLs, models, and optional speech paths. Never commit `.env`.
4. Review `pyproject.toml`, `Dockerfile`, and `GITHUB_PUBLICATION_NOTES.md` before installation: third-party IndicF5 source and GPU-specific packages were removed or left as unresolved integration points in this public preview.
5. After resolving dependencies, launch the app and inspect `GET /health` at `http://localhost:8000/health`.

**Current status:** The extracted project has not been run or tested in this packaging pass. Docker builds are not claimed to succeed without resolving the noted dependencies.

## Privacy and responsible publication

Exclude local model weights, access tokens, `.env`, textbook PDFs without appropriate rights, stored vector databases, personal student data, and proprietary third-party source code. Check third-party licenses before distributing bundled dependencies.

## Next milestones

- Create a reproducible CPU configuration and validate a GPU build.
- Restore third-party integrations via documented, licensed installation instructions.
- Add test outputs, screenshots, model evaluation, and measured latency on a specified device.
- Publish a demo with synthetic or redistributable educational content.
