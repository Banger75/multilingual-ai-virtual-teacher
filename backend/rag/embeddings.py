from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List

import onnxruntime as ort
from fastembed import TextEmbedding

from backend.config import settings


# ============================================================
# CUDA DLL SETUP
# ============================================================

def setup_cuda_dlls() -> None:
    """
    Make NVIDIA CUDA/cuDNN DLLs available to ONNX Runtime.

    This is needed on Windows when CUDA dependencies are
    installed through NVIDIA Python packages rather than
    system-wide CUDA installation.
    """

    site_packages = Path(
        __file__
    ).resolve().parents[2] / ".venv" / "Lib" / "site-packages"

    possible_dirs = [
        site_packages / "nvidia" / "cu13" / "bin" / "x86_64",
        site_packages / "nvidia" / "cublas" / "bin",
        site_packages / "nvidia" / "cudnn" / "bin",
    ]

    existing_dirs = [
        str(path)
        for path in possible_dirs
        if path.is_dir()
    ]

    if not existing_dirs:
        print(
            "WARNING: No NVIDIA Python CUDA DLL directories found."
        )
        return

    # Put CUDA DLL directories at the beginning of PATH.
    current_path = os.environ.get("PATH", "")

    new_parts = [
        path
        for path in existing_dirs
        if path not in current_path.split(os.pathsep)
    ]

    if new_parts:
        os.environ["PATH"] = (
            os.pathsep.join(new_parts)
            + os.pathsep
            + current_path
        )

    print("CUDA DLL directories:")

    for path in existing_dirs:
        print(f"  {path}")

    # Let ONNX Runtime preload CUDA dependencies.
    try:
        ort.preload_dlls(directory=existing_dirs[0])
        print("ONNX Runtime CUDA DLL preload: OK")
    except Exception as exc:
        print(
            f"ONNX Runtime CUDA DLL preload warning: {exc}"
        )


# ============================================================
# INITIALIZE CUDA BEFORE FASTEMBED
# ============================================================

if os.name == "nt":
    setup_cuda_dlls()


# ============================================================
# EMBEDDING MODEL
# ============================================================

@lru_cache(maxsize=1)
def get_embedding_model() -> TextEmbedding:
    """
    Load FastEmbed only once per Python process.

    The underlying ONNX model/session is shared by the
    entire application.
    """

    model_name = settings.embedding_model

    print("=" * 70)
    print("Loading multilingual embedding model")
    print(f"Model: {model_name}")
    print("=" * 70)

    model = TextEmbedding(
    model_name="intfloat/multilingual-e5-large",
    providers=["CPUExecutionProvider"]
    )

    # Inspect the ONNX session, not FastEmbed's requested provider list.
    try:
        print(
            "FastEmbed providers:",
        model.model.model.get_providers(),
    )
    except Exception:
        print(
            "FastEmbed model loaded successfully."
    )

    return model


# ============================================================
# MULTILINGUAL EMBEDDINGS
# ============================================================

class MultilingualEmbeddings:
    """
    Wrapper around FastEmbed for multilingual E5 embeddings.

    E5 format:

        Documents -> passage: ...
        Questions -> query: ...

    The underlying FastEmbed model is cached and shared.
    """

    def __init__(
        self,
        batch_size: int = 32,
    ):

        self.batch_size = batch_size

        print(
            f"Embedding wrapper ready "
            f"(batch size: {self.batch_size})"
        )

    # ========================================================
    # QUERY EMBEDDING
    # ========================================================

    @property
    def model(self) -> TextEmbedding:
        # Defer model loading until retrieval/indexing instead of app import.
        return get_embedding_model()

    def embed_query(
        self,
        text: str,
    ) -> List[float]:

        text = str(text or "").strip()

        if not text:
            return []

        prepared_text = f"query: {text}"

        vector = next(
            self.model.embed(
                [prepared_text],
                batch_size=1,
            )
        )

        return vector.tolist()

    # ========================================================
    # DOCUMENT EMBEDDING
    # ========================================================

    def embed_documents(
        self,
        texts: Iterable[str],
    ) -> List[List[float]]:

        cleaned_texts = []

        for text in texts:

            text = str(text or "").strip()

            if not text:
                text = " "

            cleaned_texts.append(
                f"passage: {text}"
            )

        if not cleaned_texts:
            return []

        print(
            f"Embedding {len(cleaned_texts)} textbook chunks...",
            flush=True,
        )

        vectors = []

        total = len(cleaned_texts)

        for start in range(
            0,
            total,
            self.batch_size,
        ):

            end = min(
                start + self.batch_size,
                total,
            )

            batch = cleaned_texts[start:end]

            print(
                f"Embedding chunks "
                f"{start + 1}-{end} "
                f"of {total}",
                flush=True,
            )

            batch_vectors = list(
                self.model.embed(
                    batch,
                    batch_size=min(
                        self.batch_size,
                        len(batch),
                    ),
                )
            )

            vectors.extend(
                vector.tolist()
                for vector in batch_vectors
            )

        print(
            f"Successfully created "
            f"{len(vectors)} embeddings.",
            flush=True,
        )

        return vectors
