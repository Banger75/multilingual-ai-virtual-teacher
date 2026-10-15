"""Opt-in GPU check; uses the existing embedding cache and never indexes data."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["HF_HUB_OFFLINE"] = "1"

if __name__ == "__main__":
    from backend.rag.embeddings import MultilingualEmbeddings
    embeddings = MultilingualEmbeddings()
    vector = embeddings.embed_query("Milkha Singh had what qualities?")
    providers = embeddings.model.model.model.get_providers()
    print({"dimension": len(vector), "providers": providers}, flush=True)
    if len(vector) != 1024 or "CUDAExecutionProvider" not in providers:
        raise SystemExit(1)
