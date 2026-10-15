# Application review — 2 October 2026

Reviewed the first-party backend, frontend integration, Docker configuration,
dependency configuration, and textbook indexing paths. Existing user edits were
preserved. Third-party source trees, virtual environments, model weights, and
generated media were not rewritten.

## Corrections

- Chat requires a nonblank class, subject, textbook, and question. Retrieval and
  lesson loading also reject incomplete selection instead of querying other books.
- Lesson loading retains distinct chunks sharing a PDF page, while removing exact
  duplicate chunks. This prevents silently losing lesson evidence.
- Ingestion no longer resets the collection by default. Repeated ingestion skips
  already indexed chunks, including records created with the old random IDs.
- Splitters use actual newlines. Class 10–12 filenames and Social Science metadata
  are detected correctly. TXT uploads can now be loaded and indexed.
- Uploads index the new book before returning success. Existing filenames cannot
  be silently overwritten. Malformed metadata objects no longer break the library.
- Question-bank evidence checks reject invented sentences mixed with real text.
  Answer matching rejects partial-word/numeric substring matches and preserves
  Hindi/Punjabi vowel marks. The 80% answer-word threshold is unchanged.
- Duplicate-question keys retain Hindi and Punjabi text.
- Chat reads NDJSON incrementally and handles the separate audio event. The
  mathematics board uses the canonical subject name.
- Vision receives the actual student question and correct JPEG/WebP MIME type.
  The alternate OCR explanation helper uses existing configuration fields.
- Insufficient-context replies respect Hindi/Punjabi language selection. The
  teacher prompt explicitly prohibits inferred extra personality traits.
- Embeddings load on demand, allowing the application to start without loading
  the model. Provider logging reports the actual ONNX session providers.
- Docker installs the application after its source is copied, caches dependency
  artifacts, and enables tested GPU passthrough. CPU ONNX Runtime is excluded so
  it cannot overwrite the pinned GPU runtime's Python files.

## Verification

- Full host test suite: **21 passed**, including the existing Punjabi TTS tests.
- Earlier container regression run: **17 passed**; final container verification
  is recorded below after deployment.
- All backend Python files parsed successfully; JavaScript syntax check passed.
- No duplicate HTML IDs. Stream-parser checks covered partial lines, CRLF,
  multilingual text, final lines without a newline, audio events, and cleanup.
- Corrected source in Docker returned: “Milkha Singh had qualities like patience,
  courage, devotion, and hard work.” Retrieval was constrained to Class 5 English,
  English_Class 5.pdf. A prior response included inferred extra traits; the
  corrected prompt removed those in the repeated smoke test.
- GPU smoke test: 1024-dimensional embedding, CUDAExecutionProvider active.
- Existing Qdrant collection: school_books, 1024 dimensions, 933 points at review.
  No live indexing, reset, or textbook deletion was performed during these checks.
- Compose configuration and git whitespace checks passed.

## Limits and configuration decisions

- No connected browser was available for a visual/click-through UI check. Parser,
  HTML references, HTTP serving, and API behavior were checked separately.
- Model-based answers remain probabilistic; one successful textbook question is
  not proof that all possible answers are grounded. Oral-bank validation remains
  deterministic and separate from normal chat.
- The active .env selects qwen3-8b, whereas AGENTS.md specifies
  qwen/qwen3.5-9b. A model switch requires the user's explicit approval.
- The sample .env.example still differs from the active setup (class5_books and
  multilingual-e5-small), and the configuration's fallback collection is
  class5_books. Do not replace the working .env with that sample without aligning
  it with the existing collection and embedding model. Active values were retained.
- Live Hindi/Punjabi audio, microphone capture, and vision generation were not
  exhaustively exercised. The speech unit test uses a fake model rather than
  downloading IndicF5 weights. Older logs include vision-model timeouts.
- If upload indexing fails, the saved source file remains for recovery and the
  API returns an error. Ingestion can be retried without resetting the collection.
- Existing textbook chunks are preserved; metadata fixes apply to future loading
  and do not silently rewrite existing indexed payloads.

## Reproduce checks

```powershell
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider
docker compose config --quiet
docker compose build virtual-teacher
docker compose up -d --no-deps virtual-teacher
curl.exe http://localhost:8000/health
docker compose logs --tail=100 virtual-teacher
```

`tests/live_chat_smoke.py` is an opt-in real-service test. On Windows it uses
temporary localhost endpoints; in Docker it retains the configured service URLs.
`tests/gpu_smoke.py` checks the actual embedding session and cached model.
