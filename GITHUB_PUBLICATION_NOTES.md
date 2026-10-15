# Publication and deployment notes

This portfolio package excludes bundled third-party source trees, generated data, and local models. It is **not verified as a standalone Docker build**. The original GPU-oriented Dockerfile and dependency definitions require additional integration work, notably the IndicF5 local source path. Do not claim successful build or tests without rerunning them.

- **IndicF5:** Original project includes third-party `IndicF5/` source, omitted from this publication copy. Restore it only after checking licensing and distribution rights, or replace the local `f5-tts` dependency with a suitably licensed external package. The `pyproject.toml` path source and Docker build currently expect it.
- **Hunyuan3D-2:** Original third-party source omitted; integrate it through separately documented installation rather than republishing the upstream repository.
- **CPU and GPU:** `docker-compose.yml` no longer requires GPU reservation by default, but `Dockerfile` and Python dependencies are still CUDA/GPU oriented. CPU-only operation needs a separate compatible requirements/image combination, and has **not been validated**. `docker-compose.gpu.yml` provides the optional GPU reservation setting.
- **Model settings:** `.env.example` is aligned with current `backend/config.py` defaults for the text LLM and embeddings; these models may need substantial memory. Replace values with models actually installed in LM Studio.
- **PDFs / student data:** No textbook PDFs or personal student records should be committed. Mount only data you are licensed to use.
- **Security:** Review any remaining source literals and git staging with a secret scanner before public release. No runtime tests or end-to-end builds were performed in this packaging step.
