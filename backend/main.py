from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.books import router as books_router
from backend.api.chat import router as chat_router
from backend.api.speech import router as speech_router
from backend.api.vision import router as vision_router
from backend.config import settings
from backend.api.question_paper import (
    router as question_paper_router
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

AUDIO_DIR = (
    PROJECT_ROOT /
    "data" /
    "audio" /
    "output"
)

BOOK_PAGES_DIR = (
    PROJECT_ROOT /
    "data" /
    "book_pages"
)

FRONTEND_DIR = (
    PROJECT_ROOT /
    "frontend"
)

AVATAR_3D_DIR = (
    PROJECT_ROOT /
    "avatar_3d" /
    "exports"
)

AUDIO_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

BOOK_PAGES_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    chat_router
)

app.include_router(
    speech_router
)

app.include_router(
    books_router
)

app.include_router(
    vision_router
)

app.include_router(
    question_paper_router
)

app.mount(
    "/audio",
    StaticFiles(
        directory=str(AUDIO_DIR)
    ),
    name="audio",
)

# Keep the existing frontend URL contract:
# /vision-pages/<book_id>/page_013.png
app.mount(
    "/vision-pages",
    StaticFiles(
        directory=str(BOOK_PAGES_DIR)
    ),
    name="vision-pages",
)

app.mount(
    "/frontend",
    StaticFiles(
        directory=str(FRONTEND_DIR),
        html=True,
    ),
    name="frontend",
)

app.mount(
    "/assets",
    StaticFiles(
        directory=str(FRONTEND_DIR / "assets"),
    ),
    name="assets",
)

# The 3D teacher is optional so a missing local asset never prevents the
# textbook teacher API from starting.
if AVATAR_3D_DIR.is_dir():
    app.mount(
        "/avatar-3d",
        StaticFiles(directory=str(AVATAR_3D_DIR)),
        name="avatar-3d",
    )

@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm": settings.llm_base_url,
        "qdrant": settings.qdrant_url,
        "text_model": settings.llm_model,
        "vision_model": settings.vision_model,
    }


@app.get("/")
def root():
    index = FRONTEND_DIR / "index.html"

    if index.exists():
        from fastapi.responses import FileResponse

        return FileResponse(
            index
        )

    return {
        "status": "online",
        "application": settings.app_name,
        "version": settings.app_version,
    }
