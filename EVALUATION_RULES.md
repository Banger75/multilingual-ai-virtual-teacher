# Evaluation Rules

## Purpose

The evaluator ensures that generated question-bank answers are
supported by textbook evidence.

The evaluator must be deterministic.

---

## 1. Text Normalization

Function:

_normalize_text()

Normalization includes:

- lowercase
- curly apostrophe normalization
- quotation normalization
- dash normalization
- Unicode minus normalization
- ligature normalization
- whitespace normalization

Normalization must not alter actual words.

---

## 2. Evidence Validation

Function:

_evidence_exists()

Evidence must actually occur in the lesson content.

Exact normalized evidence matching is preferred.

Sentence-level matching may be used when appropriate.

Evidence validation must reject fabricated evidence.

---

## 3. Answer Validation

Function:

_answer_supported()

The evaluator uses two levels.

### Level 1

If normalized answer is contained directly in normalized evidence:

ACCEPT

### Level 2

Otherwise perform meaningful-word comparison.

Meaningful words:

words with at least 3 characters.

Punctuation must be ignored.

Use regex word extraction rather than raw split.

---

## 4. Current Threshold

Fallback answer support requires:

80% meaningful answer-word coverage.

Formula:

required = max(
    2,
    math.ceil(len(answer_words) * 0.80),
)

The answer is accepted when:

matched >= required

---

## 5. Examples

## Supported

Evidence:

Milkha Singh showed patience, courage, devotion and hard work.

Answer:

patience courage devotion hard work

Expected:

True

---

## Unsupported

Evidence:

Milkha Singh showed patience, courage, devotion and hard work.

Answer:

Milkha Singh was a famous scientist who discovered electricity.

Expected:

False

---

## Partially Supported

Evidence:

Milkha Singh showed patience, courage, devotion and hard work.

Answer:

Milkha Singh showed patience, courage and hard work.

Expected:

True

---

## 6. Regression Requirement

Whenever evaluator logic changes, test:

- exact answer
- punctuation variation
- whitespace variation
- case variation
- supported partial answer
- unsupported answer
- evidence missing from textbook

Do not lower the validation threshold merely to make
question generation succeed.

If the LLM repeatedly produces invalid question banks,

improve the generation prompt or retry logic instead.
