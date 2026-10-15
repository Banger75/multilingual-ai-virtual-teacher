"""Opt-in read-only smoke test against the running Windows host services.

Run from the project root: .venv/Scripts/python.exe tests/live_chat_smoke.py
Uses temporary process settings; never rewrites .env or indexes data.
"""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if sys.platform == "win32":
    os.environ["LLM_BASE_URL"] = "http://127.0.0.1:1234/v1"
    os.environ["QDRANT_URL"] = "http://127.0.0.1:6333"
os.environ["HF_HUB_OFFLINE"] = "1"

if __name__ == "__main__":
    import json
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        print("health:", client.get("/health").json(), flush=True)
        response = client.post("/api/chat", json={
            "question": "Milkha Singh had what qualities?",
            "class_name": "5", "subject": "english",
            "book": "English_Class 5.pdf", "language": "English",
            "response_mode": "written",
        })
        events = [json.loads(line) for line in response.text.splitlines()]
        final = [event for event in events if event["type"] in {"done", "error"}]
        print(json.dumps(final, ensure_ascii=False), flush=True)
        if not final or final[-1]["type"] != "done":
            raise SystemExit(1)
