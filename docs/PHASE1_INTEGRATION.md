# PHASE 1 — INTELLIGENT ROUTER INTEGRATION

## 1. Add this new file

Create:

```text
backend/ai/intent_router.py
```

Use the supplied `intent_router.py`.

## 2. Replace the current frontend `isVisionQuestion()`

Your current function is too broad because it treats any occurrence of
"picture", "image", "photo", etc. as Vision.

Replace the whole function:

```javascript
function isVisionQuestion(question) {
    const text = String(question || "").trim().toLowerCase();
    if (!text) return false;

    return [
        "picture",
        "image",
        "illustration",
        "photo",
        "diagram",
        "visual"
    ].some((word) => text.includes(word));
}
```

with:

```javascript
function isVisionQuestion(question) {
  const text = String(question || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");

  if (!text) return false;

  const hasPageNumber =
    /\bpage\s*(?:number\s*)?\d+\b/i.test(text);

  const hasVisionVerb = [
    "explain",
    "describe",
    "look at",
    "what is happening",
    "what are",
    "what do you see",
    "identify",
    "analyze",
    "analyse",
  ].some((phrase) => text.includes(phrase));

  const hasVisualWord = [
    "picture",
    "image",
    "illustration",
    "photo",
    "photograph",
    "diagram",
    "visual",
  ].some((word) => text.includes(word));

  const explicitUploadedVisual =
    [
      "this image",
      "this picture",
      "this photo",
      "uploaded image",
      "uploaded picture",
      "uploaded page",
    ].some((phrase) => text.includes(phrase));

  /*
     IMPORTANT:
     "Do you have a picture of Milkha Singh?"
     must NOT go to /api/vision/explain.

     "Explain the picture on page 13"
     MUST go to Vision.
  */
  if (hasPageNumber && hasVisionVerb && hasVisualWord) {
    return true;
  }

  if (explicitUploadedVisual && (hasVisionVerb || hasVisualWord)) {
    return true;
  }

  if (
    text.includes("what is happening") &&
    (hasPageNumber || explicitUploadedVisual)
  ) {
    return true;
  }

  return false;
}
```

## 3. Expected routing after this change

| Question | Current result after Phase 1 |
|---|---|
| `Explain the picture on page 13` | Vision |
| `What is happening in the picture on page 13?` | Vision |
| `Explain this uploaded page` | Vision |
| `Explain this image` | Vision |
| `Do you have a picture of Milkha Singh?` | Normal RAG for now |
| `Who was Milkha Singh?` | Normal RAG |
| `What does page 13 say?` | Normal text path |
| `Tell me about the picture in Lesson 5` | Normal RAG |

The last two image-search cases are intentionally not connected to Internet
search yet. Phase 4 will add textbook-image search, and Phase 5 will add
controlled Internet image search.

## 4. Do NOT change these files yet

Do not change:

```text
backend/vision/analyzer.py
backend/api/vision.py
backend/rag/retriever.py
backend/config.py
```

The current page Vision implementation is already working and should remain
untouched.

## 5. Test immediately

After making the change:

```powershell
docker compose up -d --build virtual-teacher
```

Then:

```powershell
curl.exe http://localhost:8000/health
```

Open the browser and use:

### Test A

```text
Explain the picture on page 13
```

Expected:
- Vision request
- Qwen3-VL
- Picture explanation

### Test B

```text
Do you have a picture of Milkha Singh?
```

Expected:
- NO `/api/vision/explain`
- Normal textbook RAG request
- It may say it could not find the picture yet; that is expected because
  textbook-image search is Phase 4.

### Test C

```text
Who was Milkha Singh?
```

Expected:
- Normal textbook RAG

### Test D

```text
What does page 13 say?
```

Expected:
- Normal text path
- NOT Qwen3-VL

## 6. Browser cache

After changing `frontend/app.js`, use:

```text
Ctrl + Shift + R
```

The project documentation already uses this procedure for frontend changes.
