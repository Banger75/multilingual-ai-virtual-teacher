# Changelog

## 2026-08-19

### Docker / GPU

- Configured NVIDIA CUDA Docker runtime.
- Verified RTX 5060 is visible from Docker.
- Verified CUDA 13.1 container compatibility.
- Verified ONNX Runtime GPU providers.
- Verified FastEmbed CUDAExecutionProvider.

### Networking

- LM Studio is accessed from Docker through:
  <http://host.docker.internal:1234/v1>

- Qdrant is accessed internally through:
  <http://qdrant:6333>

### Backend

- FastAPI application successfully starts through Docker.
- /health endpoint verified.

### Frontend

- Fixed textbook dropdown filtering/selection workflow.
- Verified /api/books returns available textbooks.
- Fixed frontend streaming response processing.

### Question Bank

- Added robust _normalize_text() normalization.
- Improved punctuation-insensitive answer comparison.
- Changed fallback answer-support threshold from 60% to 80%.
- Added math.ceil() for threshold calculation.
- Meaningful words are extracted using regex instead of raw whitespace
  splitting.

### Current Evaluator Rule

required = max(
    2,
    math.ceil(len(answer_words) * 0.80),
)

This must be treated as a deliberate accuracy decision.
