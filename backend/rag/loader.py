from pathlib import Path
from typing import List
import re
import io

import pymupdf
import pytesseract
from PIL import Image

from langchain_core.documents import Document
from qdrant_client.models import PointStruct
from pypdf import PdfReader

# ============================================================
# PYMuPDF
# ============================================================
# IMPORTANT:
# New PyMuPDF versions recommend:
#     import pymupdf
#
# Do NOT use:
#     import fitz




# ============================================================
# CONFIGURATION
# ============================================================

# OCR rendering scale.
# 2.0 = good balance between speed and OCR quality.
OCR_SCALE = 2.0

# Minimum useful text length before considering extraction valid.
MIN_TEXT_LENGTH = 20


# ============================================================
# CLASS DETECTION
# ============================================================

def detect_class(filename: str) -> str:

    name = filename.lower()

    for number in range(1, 13):

        patterns = [
            f"class {number}",
            f"class_{number}",
            f"class{number}",
            f"_{number}.pdf",
            f"-{number}.pdf",
        ]

        if any(re.search(re.escape(pattern) + r"(?!\d)", name) for pattern in patterns):
            return str(number)

    # Example:
    # Hindi-Pustak-5-2018-03-23.pdf

    match = re.search(
        r"[-_ ](\d{1,2})(?:[-_ ]|\.pdf)",
        name,
    )

    if match:

        number = int(match.group(1))

        if 1 <= number <= 12:
            return str(number)

    return "unknown"


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language(filename: str) -> str:

    name = filename.lower()

    if "punjabi" in name:
        return "Punjabi"

    if "hindi" in name:
        return "Hindi"

    if "english" in name:
        return "English"

    # Punjabi filenames may not always contain "Punjabi".
    # Add common Punjabi book names.
    if "ganit-di-dunia" in name:
        return "Punjabi"

    if "meridunia" in name:
        return "Punjabi"

    return "Unknown"


# ============================================================
# SUBJECT DETECTION
# ============================================================

def detect_subject(filename: str) -> str:
    name = filename.lower()

    # Specific subject words should win over the book language.
    if "ganit" in name or "math" in name or "mathematics" in name:
        return "mathematics"

    if "social" in name or "sst" in name:
        return "social science"

    if "science" in name:
        return "science"

    if "meridunia" in name:
        return "environmental studies"

    if "english" in name:
        return "english"

    if "hindi" in name or "pustak" in name:
        return "hindi"

    if "punjabi" in name:
        return "punjabi"

    return "general"


# ============================================================
# PDF VALIDATION
# ============================================================

def is_valid_pdf(path: Path) -> bool:

    try:

        with open(path, "rb") as f:
            header = f.read(5)

        return header == b"%PDF-"

    except OSError:

        return False


# ============================================================
# OCR LANGUAGE
# ============================================================

def get_ocr_language(language: str) -> str:

    if language.lower() == "punjabi":
        return "pan"

    if language.lower() == "hindi":
        return "hin"

    if language.lower() == "english":
        return "eng"

    return "eng"


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:

    if not text:
        return ""

    # Replace unusual null characters.
    text = text.replace("\x00", " ")

    # Normalize excessive whitespace.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # Remove excessive blank lines.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# DETECT GARBLED PDF TEXT
# ============================================================

def is_garbled_text(
    text: str,
    language: str,
) -> bool:

    if not text:
        return True

    text = text.strip()

    if len(text) < MIN_TEXT_LENGTH:
        return True

    # --------------------------------------------------------
    # English
    # --------------------------------------------------------

    if language.lower() == "english":

        letters = re.findall(
            r"[A-Za-z]",
            text,
        )

        # If there are enough Latin characters,
        # assume extraction is probably okay.
        if len(letters) >= 10:
            return False

        return True

    # --------------------------------------------------------
    # Hindi
    # --------------------------------------------------------

    if language.lower() == "hindi":

        # Devanagari Unicode range.
        devanagari = re.findall(
            r"[\u0900-\u097F]",
            text,
        )

        # If Hindi text contains enough Devanagari,
        # normal extraction is probably valid.
        if len(devanagari) >= 5:
            return False

        # Common signs of broken PDF encoding.
        bad_patterns = [
            "Ã",
            "Â",
            "ê",
            "³",
            "ñ",
            "ð",
            "þ",
            "¿",
            "Ç",
        ]

        bad_count = sum(
            text.count(pattern)
            for pattern in bad_patterns
        )

        if bad_count >= 3:
            return True

        return True

    # --------------------------------------------------------
    # Punjabi
    # --------------------------------------------------------

    if language.lower() == "punjabi":

        # Gurmukhi Unicode range.
        gurmukhi = re.findall(
            r"[\u0A00-\u0A7F]",
            text,
        )

        # This is the most important check for your
        # Ganit-Di-Dunia PDF.
        #
        # Bad extracted text looked like:
        #
        # ê³ÜòÄ ôz¶äÆ ñÂÆ
        #
        # It contains very little/no Gurmukhi.
        if len(gurmukhi) >= 5:
            return False

        # Detect typical broken legacy PDF encoding.
        bad_patterns = [
            "ê",
            "³",
            "ñ",
            "Â",
            "Ã",
            "Ç",
            "¿",
            "ô",
            "¶",
            "Æ",
            "ð",
        ]

        bad_count = sum(
            text.count(pattern)
            for pattern in bad_patterns
        )

        if bad_count >= 2:
            return True

        # If Punjabi is expected but no Gurmukhi
        # characters are present, OCR is safer.
        return True

    # --------------------------------------------------------
    # Unknown language
    # --------------------------------------------------------

    return False


# ============================================================
# CHECK TESSERACT LANGUAGE
# ============================================================

def check_ocr_language(language: str) -> bool:

    ocr_language = get_ocr_language(
        language
    )

    try:

        available = pytesseract.get_languages(
            config=""
        )

        if ocr_language not in available:

            print(
                f"    WARNING: Tesseract language "
                f"'{ocr_language}' is not installed."
            )

            print(
                f"    Available languages: "
                f"{', '.join(available)}"
            )

            return False

        return True

    except Exception as e:

        print(
            f"    WARNING: Could not check "
            f"Tesseract languages: {e}"
        )

        return False


# ============================================================
# OCR ONE PAGE
# ============================================================

def ocr_page(
    pdf_document,
    page_number: int,
    language: str,
) -> str:

    try:

        page = pdf_document.load_page(
            page_number
        )

        # ----------------------------------------------------
        # Render PDF page as image
        # ----------------------------------------------------

        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(
                OCR_SCALE,
                OCR_SCALE,
            ),
            alpha=False,
        )

        image_bytes = pix.tobytes(
            "png"
        )

        image = Image.open(
            io.BytesIO(image_bytes)
        )

        # ----------------------------------------------------
        # OCR language
        # ----------------------------------------------------

        ocr_language = get_ocr_language(
            language
        )

        print(
            f"    OCR language: "
            f"{ocr_language}"
        )

        # ----------------------------------------------------
        # OCR configuration
        # ----------------------------------------------------
        #
        # --oem 1 = LSTM OCR engine
        # --psm 3 = automatic page segmentation
        #
        # This works well for textbook pages.
        # ----------------------------------------------------

        config = "--oem 1 --psm 3"

        text = pytesseract.image_to_string(
            image,
            lang=ocr_language,
            config=config,
        )

        return clean_text(text)

    except Exception as e:

        print(
            f"    OCR failed on page "
            f"{page_number + 1}: {e}"
        )

        return ""


# ============================================================
# LOAD PDF
# ============================================================

def load_pdf(pdf_path: str, metadata_override: dict | None = None) -> List[Document]:
    """
    Load a PDF using normal text extraction first.
    If text is missing or garbled, automatically use Tesseract OCR.
    """

    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    # --------------------------------------------------
    # Metadata
    # --------------------------------------------------

    metadata_override = metadata_override or {}

    class_name = str(
        metadata_override.get("class")
        or metadata_override.get("class_name")
        or detect_class(path.name)
    ).strip()
    class_name = re.sub(r"^class\s*", "", class_name, flags=re.I).strip()

    language = str(
        metadata_override.get("language")
        or detect_language(path.name)
    ).strip()

    subject = str(
        metadata_override.get("subject")
        or detect_subject(path.name)
    ).strip().lower()

    # Canonical subject names used by Qdrant.
    subject_aliases = {
        "math": "mathematics",
        "maths": "mathematics",
        "गणित": "mathematics",
        "english": "english",
        "hindi": "hindi",
        "punjabi": "punjabi",
        "ਪੰਜਾਬੀ": "punjabi",
        "science": "science",
        "sst": "social science",
        "social": "social science",
        "evs": "environmental studies",
    }
    subject = subject_aliases.get(subject, subject)

    language_aliases = {
        "english": "english",
        "hindi": "hindi",
        "punjabi": "punjabi",
    }
    language = language_aliases.get(language.lower(), language.lower())

    print()
    print("=" * 70)
    print(f"LOADING: {path.name}")
    print("=" * 70)

    print(f"Class: {class_name}")
    print(f"Subject: {subject}")
    print(f"Language: {language}")

    # --------------------------------------------------
    # Check Tesseract language
    # --------------------------------------------------

    ocr_available = check_ocr_language(language)

    # --------------------------------------------------
    # Open PDF
    # --------------------------------------------------

    try:
        pdf_document = pymupdf.open(str(path))

    except Exception as e:
        print(f"ERROR: Could not open PDF: {e}")
        return []

    total_pages = len(pdf_document)

    print(f"Total PDF pages: {total_pages}")

    # --------------------------------------------------
    # Try pypdf
    # --------------------------------------------------

    try:
        reader = PdfReader(str(path))

    except Exception as e:
        print("WARNING: pypdf could not read this PDF.")
        print(f"Reason: {e}")
        reader = None

    documents: List[Document] = []

    # ==================================================
    # PROCESS EACH PAGE
    # ==================================================

    for page_index in range(total_pages):

        page_number = page_index + 1
        text = ""

        # --------------------------------------------------
        # STEP 1: Normal PDF text extraction
        # --------------------------------------------------

        if reader is not None:

            try:

                if page_index < len(reader.pages):

                    text = (
                        reader
                        .pages[page_index]
                        .extract_text()
                        or ""
                    )

                    text = clean_text(text)

            except Exception:
                text = ""

        # --------------------------------------------------
        # STEP 2: Check whether OCR is required
        # --------------------------------------------------

        needs_ocr = is_garbled_text(
            text,
            language,
        )

        # --------------------------------------------------
        # STEP 3: OCR
        # --------------------------------------------------

        if needs_ocr:

            print(
                f"Page {page_number}: "
                f"Bad/garbled text -> OCR"
            )

            if ocr_available:

                text = ocr_page(
                    pdf_document,
                    page_index,
                    language,
                )

            else:

                print(
                    f"Page {page_number}: "
                    f"OCR unavailable"
                )

                text = ""

        else:

            print(
                f"Page {page_number}: "
                f"Normal PDF text"
            )

        # --------------------------------------------------
        # STEP 4: Clean final text
        # --------------------------------------------------

        text = clean_text(text)

        if not text:

            print(
                f"Page {page_number}: "
                f"No text extracted"
            )

            continue

        # --------------------------------------------------
        # STEP 5: Metadata
        # --------------------------------------------------

        metadata = {
            "source": path.name,
            "book_filename": path.name,
            "file_path": str(path),
            "page": page_number,
            "class": class_name,
            "class_level": class_name,
            "subject": subject,
            "language": language,
            "book": path.stem,
            "extraction_method": (
                "ocr"
                if needs_ocr
                else "pdf_text"
            ),
        }

        # --------------------------------------------------
        # STEP 6: LangChain Document
        # --------------------------------------------------

        documents.append(
            Document(
                page_content=text,
                metadata=metadata,
            )
        )

    # --------------------------------------------------
    # Close PDF
    # --------------------------------------------------

    pdf_document.close()

    print(
        f"Pages successfully loaded: "
        f"{len(documents)}/{total_pages}"
    )

    return documents

# ============================================================
# BOOK METADATA
# ============================================================

def infer_book_metadata(filename: str, overrides: dict | None = None) -> dict:
    overrides = overrides or {}

    class_name = str(
        overrides.get("class")
        or overrides.get("class_name")
        or detect_class(filename)
    ).strip()
    class_name = re.sub(r"^class\s*", "", class_name, flags=re.I).strip()

    language = str(
        overrides.get("language")
        or detect_language(filename)
    ).strip().lower()

    subject = str(
        overrides.get("subject")
        or detect_subject(filename)
    ).strip().lower()

    aliases = {
        "math": "mathematics",
        "maths": "mathematics",
        "गणित": "mathematics",
        "sst": "social science",
        "social": "social science",
        "evs": "environmental studies",
    }
    subject = aliases.get(subject, subject)

    return {
        "book": Path(filename).stem,
        "filename": Path(filename).name,
        "class": class_name,
        "class_name": class_name,
        "subject": subject,
        "language": language,
    }


def read_book_metadata(pdf_file: Path) -> dict:
    meta_file = pdf_file.with_suffix(pdf_file.suffix + ".meta.json")
    if not meta_file.exists():
        return {}
    try:
        import json
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"WARNING: Could not read metadata {meta_file.name}: {exc}")
        return {}


# ============================================================
# LOAD ALL BOOKS
# ============================================================

def load_book(path: str | Path, metadata_override: dict | None = None) -> List[Document]:
    path = Path(path)
    overrides = metadata_override if metadata_override is not None else read_book_metadata(path)
    if path.suffix.lower() == ".pdf":
        return load_pdf(str(path), metadata_override=overrides)
    if path.suffix.lower() == ".txt":
        text = clean_text(path.read_text(encoding="utf-8-sig"))
        if not text:
            return []
        metadata = infer_book_metadata(path.name, overrides)
        metadata.update(source=path.name, book_filename=path.name,
                        file_path=str(path), page=1, extraction_method="text")
        return [Document(page_content=text, metadata=metadata)]
    raise ValueError("Only PDF and TXT books are supported.")


def load_books(
    directory: str = "data/books",
) -> List[Document]:

    books_directory = Path(
        directory
    )

    if not books_directory.exists():

        raise FileNotFoundError(
            f"Books directory not found: "
            f"{directory}"
        )

    all_documents: List[Document] = []

    pdf_files = sorted(path for path in books_directory.iterdir()
                       if path.is_file() and path.suffix.lower() in {".pdf", ".txt"})

    print(
        f"\nFound {len(pdf_files)} textbook files:"
    )

    for pdf_file in pdf_files:

        print(
            f"  - {pdf_file.name}"
        )

    # ========================================================
    # PROCESS EACH BOOK
    # ========================================================

    for pdf_file in pdf_files:

        print()
        print("=" * 70)

        print(
            f"LOADING: {pdf_file.name}"
        )

        print("=" * 70)

        try:

            overrides = read_book_metadata(pdf_file)

            documents = load_book(
                str(pdf_file),
                metadata_override=overrides,
            )

        except Exception as e:

            print(
                f"ERROR loading "
                f"{pdf_file.name}: {e}"
            )

            continue

        if not documents:

            print(
                "  WARNING: No pages loaded."
            )

            continue

        # ----------------------------------------------------
        # Display metadata
        # ----------------------------------------------------

        first_metadata = (
            documents[0].metadata
        )

        print(
            f"  Book: "
            f"{pdf_file.stem}"
        )

        print(
            f"  Class: "
            f"{first_metadata['class']}"
        )

        print(
            f"  Subject: "
            f"{first_metadata['subject']}"
        )

        print(
            f"  Language: "
            f"{first_metadata['language']}"
        )

        print(
            f"  Pages loaded: "
            f"{len(documents)}"
        )

        all_documents.extend(
            documents
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print("=" * 70)

    print(
        f"TOTAL PAGES LOADED: "
        f"{len(all_documents)}"
    )

    print("=" * 70)

    return all_documents
