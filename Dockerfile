FROM nvidia/cuda:13.1.2-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# ============================================================
# SYSTEM DEPENDENCIES
# ============================================================

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-pip \
        curl \
        ca-certificates \
        ffmpeg \
        libgomp1 \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-hin \
        tesseract-ocr-pan \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# INSTALL UV
# ============================================================

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

# Verify uv
RUN uv --version

# ============================================================
# PROJECT DEPENDENCIES
# ============================================================

COPY pyproject.toml uv.lock README.md ./

# IndicF5 is included as local source so Punjabi TTS has no paid service
# dependency. Its prompt audio is copied with the application below.
COPY integrations/IndicF5 ./IndicF5

RUN --mount=type=cache,id=virtual_teacher_uv,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --link-mode=copy

# Use project virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# ============================================================
# APPLICATION
# ============================================================

COPY backend ./backend
COPY frontend ./frontend
COPY main.py ./main.py
RUN --mount=type=cache,id=virtual_teacher_uv,target=/root/.cache/uv \
    uv sync --frozen --no-dev --link-mode=copy
# Exported browser asset only; Blender source files stay outside the image.
COPY avatar_3d/exports ./avatar_3d/exports

# ============================================================
# REQUIRED DIRECTORIES
# ============================================================

RUN mkdir -p \
    /app/data/audio/input \
    /app/data/audio/output \
    /app/data/books \
    /app/data/processed \
    /app/tools/piper/models \
    /app/tools/whisper/models

# ============================================================
# NVIDIA CUDA
# ============================================================

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

EXPOSE 8000

# ============================================================
# START APPLICATION
# ============================================================

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
