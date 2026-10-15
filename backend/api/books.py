from pathlib import Path
import json
import shutil

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from starlette.concurrency import run_in_threadpool

from backend.rag.loader import infer_book_metadata
from backend.rag.index_documents import index_book
from backend.vision.page_store import build_book_page_cache


router = APIRouter(prefix="/api/books", tags=["Books"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOOKS_DIR = PROJECT_ROOT / "data" / "books"
BOOKS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt"}


def metadata_path(book_path: Path) -> Path:
    return book_path.with_suffix(book_path.suffix + ".meta.json")


@router.get("")
async def list_books():
    books = []

    for path in sorted(BOOKS_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        overrides = {}
        meta_file = metadata_path(path)
        if meta_file.exists():
            try:
                overrides = json.loads(
                    meta_file.read_text(encoding="utf-8")
                )
                if not isinstance(overrides, dict):
                    overrides = {}
            except Exception:
                overrides = {}

        meta = infer_book_metadata(
            path.name,
            overrides,
        )

        books.append(
            {
                "name": path.name,
                "filename": path.name,
                "extension": path.suffix.lower(),
                **meta,
            }
        )

    return {"books": books}


@router.post("/upload")
async def upload_book(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    class_name: str | None = Form(None),
    subject: str | None = Form(None),
):
    if not file.filename:
        raise HTTPException(
            400,
            "No filename provided.",
        )

    name = Path(file.filename).name
    suffix = Path(name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            "Only PDF and TXT books are supported.",
        )

    destination = BOOKS_DIR / name

    if destination.exists():
        await file.close()
        raise HTTPException(409, "A textbook with this filename already exists. Use a new filename.")

    try:
        with destination.open("xb") as buffer:
            shutil.copyfileobj(
                file.file,
                buffer,
            )

        metadata = infer_book_metadata(
            name,
            {
                "title": title,
                "class_name": class_name,
                "subject": subject,
            },
        )

        metadata_path(destination).write_text(
            json.dumps(
                metadata,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        page_cache = None

        # Page-image caching is a PDF-only operation.
        # It happens during upload, so every uploaded textbook is ready
        # for vision requests immediately after a successful upload.
        if suffix == ".pdf":
            print("=" * 70)
            print(
                f"BUILDING PAGE IMAGE CACHE: {name}"
            )
            print("=" * 70)

            page_cache = await run_in_threadpool(build_book_page_cache,
                name,
                force=True,
                scale=1.5,
            )

            print("=" * 70)
            print(
                f"PAGE IMAGE CACHE READY: {name} "
                f"({page_cache['page_count']} pages)"
            )
            print("=" * 70)

        indexed_chunks = await run_in_threadpool(index_book, destination, metadata)

    except Exception as exc:
        raise HTTPException(
            500,
            f"Could not save/index book: {exc}",
        ) from exc

    finally:
        await file.close()

    response = {
        "success": True,
        "name": name,
        "filename": name,
        "indexed_chunks": indexed_chunks,
        **metadata,
    }

    if page_cache:
        response["page_cache"] = {
            "book_id": page_cache["book_id"],
            "page_count": page_cache["page_count"],
            "directory": (
                f"data/book_pages/"
                f"{page_cache['book_id']}"
            ),
            "metadata": "pages.json",
        }

    return response


@router.delete("/{filename}")
async def delete_book(filename: str):
    path = BOOKS_DIR / Path(filename).name

    if not path.exists():
        raise HTTPException(
            404,
            "Book not found.",
        )

    path.unlink()
    metadata_path(path).unlink(
        missing_ok=True
    )

    return {
        "success": True,
        "filename": path.name,
    }
