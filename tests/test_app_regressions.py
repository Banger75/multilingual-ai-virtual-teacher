"""Offline regressions: run with python -m unittest discover -s tests -p test_app_regressions.py."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch

from backend.ai import lesson_resolver, question_bank
from backend.rag import loader, retriever


class GroundingTests(unittest.TestCase):
    evidence = "Milkha Singh showed patience, courage, devotion and hard work."

    def test_supported_answers(self):
        for answer in ["patience", "patience courage devotion hard work",
                       "PATIENCE, COURAGE, DEVOTION AND HARD WORK",
                       "patience\n courage devotion hard work",
                       "Milkha Singh showed patience, courage and hard work."]:
            with self.subTest(answer=answer):
                self.assertTrue(question_bank._answer_supported(answer, self.evidence))

    def test_unsupported_answers(self):
        self.assertFalse(question_bank._answer_supported(
            "Milkha Singh was a famous scientist who discovered electricity.", self.evidence))
        self.assertFalse(question_bank._answer_supported("19", "The year was 2019."))
        self.assertFalse(question_bank._answer_supported("art", "He used a cart."))

    def test_evidence_must_not_include_invented_sentences(self):
        self.assertFalse(question_bank._evidence_exists(self.evidence + " He flew.", self.evidence))
        self.assertFalse(question_bank._evidence_exists("", self.evidence))
        self.assertTrue(question_bank._evidence_exists("Milkha Singh’s\n courage", "Milkha Singh's courage"))

    def test_multilingual_duplicate_keys(self):
        for first, second in [("भारत कहाँ है?", "नाम क्या है?"), ("ਨਾਮ ਕੀ ਹੈ?", "ਘਰ ਕਿੱਥੇ ਹੈ?")]:
            self.assertTrue(question_bank._question_key(first))
            self.assertNotEqual(question_bank._question_key(first), question_bank._question_key(second))
        self.assertEqual(question_bank._question_key("What qualities?"), question_bank._question_key("WHAT qualities!"))

    def test_multilingual_answer_words_preserve_vowel_marks(self):
        for answer, evidence in [("साहस मेहनत", "साहस, मेहनत"), ("ਹਿੰਮਤ ਮਿਹਨਤ", "ਹਿੰਮਤ, ਮਿਹਨਤ")]:
            with self.subTest(answer=answer):
                self.assertEqual(question_bank._meaningful_words(answer), answer.split())
                self.assertTrue(question_bank._answer_supported(answer, evidence))

    def test_duplicate_and_missing_evidence_rejected(self):
        item = dict(question="What qualities?", answer="patience", evidence=self.evidence, difficulty="easy")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            question_bank._validate_question_bank({"questions": [item.copy(), item.copy()]}, self.evidence, 2)
        with self.assertRaisesRegex(ValueError, "evidence"):
            question_bank._validate_question_bank({"questions": [{**item, "evidence": ""}]}, self.evidence, 1)

    def test_metadata_detection(self):
        for number in range(1, 13):
            self.assertEqual(loader.detect_class(f"English_Class {number}.pdf"), str(number))
        self.assertEqual(loader.detect_subject("Social Science_Class 5.pdf"), "social science")

    def test_txt_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "English_Class 10.txt"
            path.write_text(self.evidence, encoding="utf-8")
            documents = loader.load_book(path)
        self.assertEqual(documents[0].page_content, self.evidence)
        self.assertEqual(documents[0].metadata["class"], "10")

    def test_vision_receives_question_and_correct_image_type(self):
        from backend.vision import analyzer
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.jpg"
            path.write_bytes(b"mock-image")
            with patch.object(analyzer.requests, "post") as post:
                post.return_value.json.return_value = {"choices": [{"message": {"content": "Two birds."}}]}
                self.assertEqual(analyzer.analyze_page_image(path, "English", "How many birds?"), "Two birds.")
                content = post.call_args.kwargs["json"]["messages"][0]["content"]
                self.assertIn("How many birds?", content[0]["text"])
                self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_all_settings_references_exist(self):
        from backend.config import settings
        for path in Path("backend").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "settings":
                    self.assertTrue(hasattr(settings, node.attr), f"{path}: settings.{node.attr}")

    def test_upload_indexes_new_book_and_preserves_existing_file(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        with tempfile.TemporaryDirectory() as directory, patch("backend.api.books.BOOKS_DIR", Path(directory)), patch(
            "backend.api.books.index_book", return_value=1
        ) as index, TestClient(app) as client:
            response = client.post("/api/books/upload", files={"file": ("English_Class 5.txt", self.evidence)},
                                   data={"class_name": "5", "subject": "English"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["indexed_chunks"], 1)
            index.assert_called_once()
            response = client.post("/api/books/upload", files={"file": ("English_Class 5.txt", "replacement")})
            self.assertEqual(response.status_code, 409)
            self.assertEqual((Path(directory) / "English_Class 5.txt").read_text(), self.evidence)

    def test_indexing_does_not_reset_by_default(self):
        from backend.rag import ingest, index_documents
        from langchain_core.documents import Document
        for module, function in [(ingest, ingest.ingest_books), (index_documents, index_documents.index_books)]:
            with patch.object(module, "load_books", return_value=[Document(page_content=self.evidence)]), patch.object(
                module, "reset_collection"
            ) as reset, patch.object(module, "QdrantVectorStore"):
                function()
                reset.assert_not_called()

    def test_reingestion_skips_existing_chunks_without_deleting(self):
        from backend.rag import vectorstore
        from langchain_core.documents import Document
        metadata = {"class": "5", "subject": "english", "book": "English_Class 5", "page": 1}
        old = Document(page_content=self.evidence, metadata=metadata)
        new = Document(page_content="New textbook paragraph", metadata=metadata)
        records = [SimpleNamespace(payload={"page": 1, "text": self.evidence})]
        with patch.object(vectorstore, "create_collection_if_not_exists"), patch.object(
            vectorstore.client, "scroll", return_value=(records, None)
        ), patch.object(vectorstore.embedding_model, "embed_documents", return_value=[[0.1]]) as embed, patch.object(
            vectorstore.client, "upsert"
        ) as upsert, patch.object(vectorstore.client, "delete_collection") as delete:
            vectorstore.QdrantVectorStore().add_documents([old, new, new])
        embed.assert_called_once_with([new.page_content])
        self.assertEqual(len(upsert.call_args.kwargs["points"]), 1)
        delete.assert_not_called()

    def test_missing_selection_does_not_search(self):
        with patch.object(retriever.client, "query_points") as query:
            with self.assertRaises(ValueError):
                retriever.retrieve_context("Who?", class_name="5", subject="english")
            query.assert_not_called()

    def test_missing_context_does_not_call_llm_and_respects_language(self):
        from backend.ai import llm
        with patch.object(llm, "_get_context", return_value=None), patch.object(llm, "llm") as model:
            answer = "".join(llm.stream_teacher("Who?", "5", "english", "missing.pdf", "Hindi"))
            self.assertIn("पाठ्यपुस्तक", answer)
            model.stream.assert_not_called()

    def test_retrieval_keeps_all_selection_filters(self):
        with patch.object(retriever.embedding_model, "embed_query", return_value=[0.1]), patch.object(
            retriever.client, "query_points", return_value=SimpleNamespace(points=[])
        ) as query:
            retriever.retrieve_context("Who?", class_name="Class 5", subject="English", book="English_Class 5.pdf")
            conditions = query.call_args.kwargs["query_filter"].must
            self.assertEqual({c.key: c.match.value for c in conditions},
                             {"class": "5", "subject": "english", "book": "English_Class 5"})

    def test_lesson_keeps_distinct_chunks_on_same_page(self):
        records = [SimpleNamespace(payload={"page": 1, "text": text}) for text in
                   ["Lesson 1: Courage", self.evidence, self.evidence]]
        with patch.object(lesson_resolver.client, "scroll", return_value=(records, None)):
            pages = lesson_resolver._load_book_pages("5", "english", "English_Class 5.pdf")
        self.assertEqual(len(pages), 1)
        self.assertIn("Lesson 1", pages[0]["text"])
        self.assertEqual(pages[0]["text"].count(self.evidence), 1)

    def test_backend_syntax(self):
        for path in Path("backend").rglob("*.py"):
            with self.subTest(path=str(path)):
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))

    def test_health_and_stream_contract(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        with TestClient(app) as client:
            self.assertEqual(client.get("/health").json()["status"], "ok")
            self.assertEqual(client.post("/api/chat", json={"question": "Who?"}).status_code, 422)
            with patch("backend.api.chat.stream_teacher", return_value=iter([self.evidence])), patch(
                "backend.api.chat.text_to_speech", return_value="answer.wav"
            ):
                response = client.post("/api/chat", json=dict(question="Milkha Singh had what qualities?",
                    class_name="5", subject="english", book="English_Class 5.pdf", response_mode="both"))
            events = [json.loads(line) for line in response.text.splitlines()]
            self.assertEqual([e["type"] for e in events], ["chunk", "done", "audio"])
            self.assertEqual(events[1]["answer"], self.evidence)
            self.assertEqual(events[2]["audio_url"], "/audio/answer.wav")


if __name__ == "__main__":
    unittest.main()
