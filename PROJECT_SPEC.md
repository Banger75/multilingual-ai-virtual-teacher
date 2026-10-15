# Subject Specific AI Virtual Teacher

## Project Specification

## 1. Objective

Build a multilingual AI virtual teacher for school students.

The teacher should explain textbook content using the student's
selected class, subject, textbook and language.

The system should provide reliable textbook-grounded answers rather
than behaving as a general chatbot.

---

## 2. Student Workflow

Student:

1. Opens the virtual teacher.
2. Selects class.
3. Selects subject.
4. Selects language.
5. Selects textbook.
6. Enters a question or records a question.
7. Presses Ask Teacher.
8. Receives the answer.
9. Optionally receives audio.
10. Optionally sees visual/whiteboard teaching.

---

## 3. Supported Content

Initial focus:

- Class 5
- English
- Hindi
- Punjabi

The architecture should support adding:

- additional classes
- additional subjects
- additional textbooks
- additional languages

without rewriting the core system.

---

## 4. Core AI Pipeline

Question
    ↓
Selected textbook
    ↓
Retrieval
    ↓
Relevant textbook context
    ↓
LLM
    ↓
Grounded answer
    ↓
Student

---

## 5. Accuracy

The application must prioritize:

1. Correctness
2. Textbook grounding
3. Appropriate student-level explanation
4. Language correctness
5. Clear presentation

Fluent hallucinated answers are unacceptable.

---

## 6. Question Bank

The oral-test question bank must generate questions from the
selected lesson.

Every generated question must contain evidence.

Evidence must be verified against the textbook.

Answers must be checked against their evidence.

Duplicate questions must be rejected.

---

## 7. Future Features

Possible future features:

- oral tests
- adaptive questioning
- difficulty adjustment
- student progress
- teacher dashboard
- lesson summaries
- quizzes
- MCQs
- fill-in-the-blanks
- pronunciation practice
- visual explanations
- whiteboard generation
- student performance analytics

Future features must not weaken textbook grounding.
