from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import fitz


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOOKS_DIR = PROJECT_ROOT / "data" / "books"
BOOK_PAGES_DIR = PROJECT_ROOT / "data" / "book_pages"

PAGE_NUMBER_RE = re.compile(r"^\s*(\d{1,4})\s*$")


def _book_id(book_name: str) -> str:
    """
    Stable folder name for a book.

    The filename is included for readability and a short hash prevents
    collisions when two books have similar names.
    """
    stem = Path(book_name).stem
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "book"
    digest = hashlib.sha1(book_name.encode("utf-8")).hexdigest()[:10]
    return f"{safe}_{digest}"


def book_page_dir(book_name: str) -> Path:
    return BOOK_PAGES_DIR / _book_id(book_name)


def pages_json_path(book_name: str) -> Path:
    return book_page_dir(book_name) / "pages.json"


def _first_nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _printed_page_candidates(lines: list[str]) -> list[int]:
    values: list[int] = []

    # Most school PDFs expose the printed page number as a standalone line.
    for line in lines[:8]:
        match = PAGE_NUMBER_RE.match(line)
        if match:
            number = int(match.group(1))
            if 1 <= number <= 2000:
                values.append(number)

    return values


def _detect_printed_page(page: fitz.Page, pdf_index: int) -> int | None:
    """
    Detect the printed page number from extracted page text.

    We intentionally keep this conservative. If the PDF does not expose a
    printed page number, the metadata records null instead of pretending
    that PDF index == printed page.
    """
    text = page.get_text("text") or ""
    lines = _first_nonempty_lines(text)

    candidates = _printed_page_candidates(lines)

    if candidates:
        return candidates[0]

    # Some PDFs place the page number at the very end of the page.
    for line in reversed(lines[-8:]):
        match = PAGE_NUMBER_RE.match(line)
        if match:
            number = int(match.group(1))
            if 1 <= number <= 2000:
                return number

    return None


def _render_page(page: fitz.Page, output: Path, scale: float = 1.5) -> None:
    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale),
        alpha=False,
    )
    pixmap.save(str(output))


def build_book_page_cache(
    book_name: str,
    *,
    force: bool = False,
    scale: float = 1.5,
) -> dict[str, Any]:
    """
    Render every PDF page once and create pages.json.

    Returns metadata suitable for logging/API responses.
    """
    pdf_path = (BOOKS_DIR / Path(book_name).name).resolve()

    if pdf_path.parent != BOOKS_DIR.resolve():
        raise ValueError("Invalid textbook path.")

    if not pdf_path.exists():
        raise FileNotFoundError(f"Textbook not found: {pdf_path.name}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Page image cache is currently supported for PDF books only.")

    output_dir = book_page_dir(pdf_path.name)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = output_dir / "pages.json"

    if metadata_path.exists() and not force:
        try:
            existing = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (
                existing.get("source", {}).get("name") == pdf_path.name
                and existing.get("source", {}).get("size") == pdf_path.stat().st_size
                and existing.get("source", {}).get("modified_ns") == pdf_path.stat().st_mtime_ns
                and existing.get("pages")
            ):
                return existing
        except Exception:
            pass

    # Remove stale page images before rebuilding.
    for image in output_dir.glob("page_*.png"):
        image.unlink(missing_ok=True)

    pages: list[dict[str, Any]] = []

    with fitz.open(str(pdf_path)) as pdf:
        total = len(pdf)

        for pdf_index in range(total):
            page = pdf[pdf_index]

            printed_page = _detect_printed_page(
                page,
                pdf_index,
            )

            filename = f"page_{pdf_index + 1:03d}.png"
            output = output_dir / filename

            _render_page(
                page,
                output,
                scale=scale,
            )

            pages.append(
                {
                    "pdf_index": pdf_index + 1,
                    "pdf_index_zero_based": pdf_index,
                    "printed_page": printed_page,
                    "image": filename,
                    "image_url": (
                        f"/vision-pages/"
                        f"{_book_id(pdf_path.name)}/"
                        f"{filename}"
                    ),
                }
            )

            print(
                f"BOOK PAGE CACHE: {pdf_path.name} "
                f"{pdf_index + 1}/{total} -> {filename} "
                f"printed_page={printed_page}"
            )

    metadata = {
        "version": 1,
        "book_id": _book_id(pdf_path.name),
        "book": pdf_path.name,
        "source": {
            "name": pdf_path.name,
            "size": pdf_path.stat().st_size,
            "modified_ns": pdf_path.stat().st_mtime_ns,
        },
        "page_count": len(pages),
        "image_scale": scale,
        "pages": pages,
    }

    metadata_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return metadata


def load_book_page_cache(book_name: str) -> dict[str, Any] | None:
    path = pages_json_path(book_name)

    if not path.exists():
        return None

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return None


def find_cached_page(
    book_name: str,
    printed_page: int,
) -> dict[str, Any] | None:
    metadata = load_book_page_cache(book_name)

    if not metadata:
        return None

    for page in metadata.get("pages", []):
        if page.get("printed_page") == printed_page:
            return page

    return None


def build_all_book_page_caches(
    *,
    force: bool = False,
    scale: float = 1.5,
) -> None:
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)

    for pdf in sorted(BOOKS_DIR.glob("*.pdf")):
        try:
            build_book_page_cache(
                pdf.name,
                force=force,
                scale=scale,
            )
        except Exception as exc:
            print(
                f"BOOK PAGE CACHE FAILED: {pdf.name}: {exc}"
            )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build persistent page-image caches for textbook PDFs."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Build caches for every PDF in data/books.",
    )
    parser.add_argument(
        "--book",
        help="Build the cache for one PDF filename.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-render pages even when pages.json is already current.",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.5,
        help="PDF render scale. Default: 1.5",
    )

    args = parser.parse_args()

    if args.all:
        build_all_book_page_caches(
            force=args.force,
            scale=args.scale,
        )
    elif args.book:
        result = build_book_page_cache(
            args.book,
            force=args.force,
            scale=args.scale,
        )
        print(
            json.dumps(
                {
                    "book": result["book"],
                    "page_count": result["page_count"],
                    "book_id": result["book_id"],
                },
                indent=2,
            )
        )
    else:
        parser.error("Use --all or --book.")
